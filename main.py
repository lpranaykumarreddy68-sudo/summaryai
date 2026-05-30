"""
Main FastAPI Application — Decoupled, asynchronous backend for the AI Study Companion.
Manages file uploads, on-demand RAG chat querying, background document/media workers,
and session restores, serving a fast, lightweight dashboard statically.
"""

import os
import uuid
from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from dotenv import load_dotenv

from database import init_db, get_db, StudySession, ChatMessage, Flashcard, GenerationTask
from document_processor import extract_text_from_bytes, save_vector_store, load_vector_store
from utils.llm_provider import get_llm, get_embeddings
from generators import generate_pdf_task, generate_ppt_task, generate_audio_task, generate_flashcards_task

# Load environment configs
load_dotenv()

# Initialize Database tables
init_db()

# Create FastAPI app
app = FastAPI(
    title="AI Study Companion API",
    description="Asynchronous high-concurrency study asset generator API.",
    version="2.0.0"
)

# Enable CORS for standard web client interactions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure static directories exist
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "exports"), exist_ok=True)
os.makedirs(os.path.join(STATIC_DIR, "vector_stores"), exist_ok=True)

# Mount static folder
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


# ── Serve Frontend ──────────────────────────────────────────────────────────
@app.get("/")
async def serve_frontend():
    """Serve the static Tailwind HTML/JS dashboard at the root URL."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "AI Study Companion API is online. Place index.html in the static folder."}


# ── Endpoint: Upload Study Material ──────────────────────────────────────────
@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload a study file (PDF or TXT).
    Extracts text, builds FAISS index, saves index to disk under session_id,
    persists session metadata in SQLite, and returns session details.
    """
    try:
        # Read file bytes
        file_bytes = await file.read()
        filename = file.filename

        # Extract text from bytes
        raw_text = extract_text_from_bytes(file_bytes, filename)
        
        if not raw_text or len(raw_text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Document is empty or contains too little text.")

        # Generate unique session ID
        session_id = str(uuid.uuid4())

        # Load API keys and build vector store index on disk
        provider = os.getenv("AI_PROVIDER", "gemini").lower().strip()
        api_key = os.getenv("GOOGLE_API_KEY" if provider == "gemini" else "OPENAI_API_KEY", "")
        
        if not api_key:
            raise HTTPException(status_code=500, detail="AI Provider API key is missing. Please check .env configuration.")
            
        embeddings = get_embeddings(provider, api_key)
        
        # Save vector store to disk (protects server RAM under concurrent users)
        save_vector_store(session_id, raw_text, embeddings)

        # Calculate word and char counts
        char_count = len(raw_text)
        word_count = len(raw_text.split())

        # Persist session metadata in SQLite database
        session_record = StudySession(
            session_id=session_id,
            file_name=filename,
            char_count=char_count,
            word_count=word_count
        )
        db.add(session_record)
        db.commit()
        db.refresh(session_record)

        # Store the raw text locally temporarily so background tasks can read it without database bloat
        raw_text_path = os.path.join(STATIC_DIR, "vector_stores", session_id, "raw_text.txt")
        with open(raw_text_path, "w", encoding="utf-8") as f:
            f.write(raw_text)

        return {
            "session_id": session_id,
            "file_name": filename,
            "char_count": char_count,
            "word_count": word_count,
            "status": "ready"
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to process document: {str(e)}")


# ── Endpoint: Async Chat (RAG) Query ──────────────────────────────────────────
@app.post("/api/chat")
async def chat_with_tutor(
    session_id: str = Form(...),
    query: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Ask a question about the document context.
    Loads FAISS index from disk on-demand, queries context, prompts LLM,
    records chat message log in SQLite, and returns response.
    """
    # Verify session exists
    session_record = db.query(StudySession).filter(StudySession.session_id == session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        # Load API key and LLM
        provider = os.getenv("AI_PROVIDER", "gemini").lower().strip()
        api_key = os.getenv("GOOGLE_API_KEY" if provider == "gemini" else "OPENAI_API_KEY", "")
        
        embeddings = get_embeddings(provider, api_key)
        llm = get_llm(provider, api_key)

        # Load FAISS index on-demand from disk (unloads immediately after query completes)
        vector_store = load_vector_store(session_id, embeddings)
        docs = vector_store.similarity_search(query, k=4)
        context = "\n\n".join([doc.page_content for doc in docs])

        # Retrieve last 6 messages of chat history from SQLite database
        history_records = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.desc()).limit(6).all()
        history_records.reverse()  # Restore chronological order

        history_text = ""
        for msg in history_records:
            role_label = "Student" if msg.role == "user" else "AI Tutor"
            history_text += f"{role_label}: {msg.content}\n"

        rag_prompt = f"""You are a knowledgeable and helpful AI study tutor. Answer the student's 
question accurately based on the provided document context. If the answer cannot be found 
in the context, say so honestly.

Document Context:
{context}

Recent Conversation:
{history_text}

Student's Question: {query}

Provide a clear, helpful answer:"""

        # Ask LLM
        response = llm.invoke([HumanMessage(content=rag_prompt)])
        answer = response.content

        # Save user message & tutor answer to SQLite database
        user_msg = ChatMessage(session_id=session_id, role="user", content=query)
        ai_msg = ChatMessage(session_id=session_id, role="ai", content=answer)
        db.add(user_msg)
        db.add(ai_msg)
        db.commit()

        return {"role": "ai", "content": answer}

    except Exception as e:
        db.rollback()
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            raise HTTPException(
                status_code=429,
                detail="Gemini API Quota Exceeded: The configured Google API key has exceeded the daily free tier limit of 20 requests. Please configure an alternative key in your .env file or retry tomorrow."
            )
        raise HTTPException(status_code=500, detail=f"RAG query failed: {err_msg}")


# ── Endpoint: Spin off Background Generation Task ───────────────────────────
@app.post("/api/generate/{asset_type}")
async def trigger_generation(
    asset_type: str,
    background_tasks: BackgroundTasks,
    session_id: str = Form(...),
    db: Session = Depends(get_db)
):
    """
    Spin off background task for PDF summary, PPT slides, MP3 audio, or study flashcards.
    Immediately returns a unique task tracking ID and registers status as 'processing'.
    """
    if asset_type not in ["pdf", "ppt", "audio", "flashcards"]:
        raise HTTPException(status_code=400, detail="Invalid asset type. Choose 'pdf', 'ppt', 'audio', or 'flashcards'.")

    # Verify session
    session_record = db.query(StudySession).filter(StudySession.session_id == session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Session not found.")

    try:
        # Read the raw text cached in the session folder
        raw_text_path = os.path.join(STATIC_DIR, "vector_stores", session_id, "raw_text.txt")
        if not os.path.exists(raw_text_path):
            raise FileNotFoundError("Raw text cache missing.")
            
        with open(raw_text_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        # Generate unique Task ID
        task_id = str(uuid.uuid4())

        # Register task in the SQLite database
        task_record = GenerationTask(
            task_id=task_id,
            session_id=session_id,
            asset_type=asset_type,
            status="processing"
        )
        db.add(task_record)
        db.commit()

        # Spin off background task workers
        if asset_type == "pdf":
            background_tasks.add_task(generate_pdf_task, raw_text, task_id)
        elif asset_type == "ppt":
            background_tasks.add_task(generate_ppt_task, raw_text, task_id)
        elif asset_type == "audio":
            background_tasks.add_task(generate_audio_task, raw_text, task_id)
        elif asset_type == "flashcards":
            background_tasks.add_task(generate_flashcards_task, raw_text, session_id, task_id)

        return {
            "task_id": task_id,
            "status": "processing",
            "message": f"Background task registered for {asset_type} generation."
        }

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to initiate task: {str(e)}")


# ── Endpoint: Poll Task Status ──────────────────────────────────────────────
@app.get("/api/status/{task_id}")
async def get_task_status(
    task_id: str,
    db: Session = Depends(get_db)
):
    """
    Allow the frontend to poll for task status.
    Returns status ('processing', 'completed', 'failed') and final download file link if completed.
    """
    task = db.query(GenerationTask).filter(GenerationTask.task_id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    res = {
        "task_id": task.task_id,
        "asset_type": task.asset_type,
        "status": task.status,
        "updated_at": task.updated_at.isoformat()
    }
    if task.status == "completed":
        res["file_url"] = task.file_url
    elif task.status == "failed":
        res["error"] = task.error_message

    return res


# ── Endpoint: Get Session details (restore) ─────────────────────────────────
@app.get("/api/session/{session_id}")
async def get_session_details(
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    Restore study session metadata, chat history logs, and completed flashcards.
    Allows easy restoration of dashboard context when the user refreshes or re-enters.
    """
    session_record = db.query(StudySession).filter(StudySession.session_id == session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="Session not found.")

    # Fetch messages
    messages = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at.asc()).all()
    message_list = [{"role": msg.role, "content": msg.content} for msg in messages]

    # Fetch flashcards
    flashcard_records = db.query(Flashcard).filter(Flashcard.session_id == session_id).all()
    flashcard_list = [{"question": fc.question, "answer": fc.answer} for fc in flashcard_records]

    # Fetch completed asset tasks
    completed_tasks = db.query(GenerationTask).filter(
        GenerationTask.session_id == session_id,
        GenerationTask.status == "completed"
    ).all()
    
    completed_assets = {t.asset_type: t.file_url for t in completed_tasks}

    return {
        "session_id": session_id,
        "file_name": session_record.file_name,
        "char_count": session_record.char_count,
        "word_count": session_record.word_count,
        "chat_history": message_list,
        "flashcards": flashcard_list,
        "completed_assets": completed_assets
    }
