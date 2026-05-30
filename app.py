"""
AI Study Companion — Main Streamlit Application
Upload a PDF or TXT file, ask questions via RAG-powered chat,
and generate study resources on demand.
"""

import os
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage

from utils.document_processor import extract_text, build_vector_store
from utils.llm_provider import get_llm, get_embeddings
from utils.pdf_generator import generate_pdf_summary
from utils.ppt_generator import generate_ppt_slides
from utils.audio_generator import generate_audio_summary
from utils.flashcard_generator import generate_flashcards

# ── Load environment variables ──────────────────────────────────────────────
load_dotenv()

# ── .env file path ──────────────────────────────────────────────────
ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def _save_key_to_env(prov: str, key: str):
    """Write / update the API key in the .env file so it persists across restarts."""
    env_vars = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    env_vars[k.strip()] = v.strip()

    env_vars["AI_PROVIDER"] = prov
    if prov == "gemini":
        env_vars["GOOGLE_API_KEY"] = key
    else:
        env_vars["OPENAI_API_KEY"] = key

    with open(ENV_FILE, "w") as f:
        f.write("# AI Study Companion — Environment Configuration\n\n")
        for k, v in env_vars.items():
            f.write(f"{k}={v}\n")


# ── Backend Configuration (from .env) ───────────────────────────────────────
provider = os.getenv("AI_PROVIDER", "gemini").lower().strip()
if provider == "gemini":
    api_key = os.getenv("GOOGLE_API_KEY", "")
elif provider == "openai":
    api_key = os.getenv("OPENAI_API_KEY", "")
else:
    api_key = os.getenv("GOOGLE_API_KEY", "")
    provider = "gemini"

has_key = bool(api_key and api_key.strip() and not api_key.startswith("your-"))

# ── Page Configuration ──────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Study Companion",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* ── Global ── */
    .stApp {
        font-family: 'Inter', sans-serif;
    }

    /* ── Header ── */
    .app-header {
        background: linear-gradient(135deg, #1e3a5f 0%, #0f172a 50%, #1e1b4b 100%);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        position: relative;
        overflow: hidden;
    }
    .app-header::before {
        content: '';
        position: absolute;
        top: -50%;
        right: -20%;
        width: 400px;
        height: 400px;
        background: radial-gradient(circle, rgba(99,102,241,0.15) 0%, transparent 70%);
        border-radius: 50%;
    }
    .app-header h1 {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 700;
        margin: 0;
        letter-spacing: -0.5px;
    }
    .app-header p {
        color: #94a3b8;
        font-size: 1rem;
        margin: 0.4rem 0 0 0;
        font-weight: 400;
    }

    /* ── Upload Zone ── */
    .upload-zone {
        background: linear-gradient(135deg, #f0f9ff 0%, #ede9fe 100%);
        border: 2px dashed #a5b4fc;
        border-radius: 14px;
        padding: 1.5rem;
        text-align: center;
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
    }

    /* ── Chat Messages ── */
    .chat-user {
        background: linear-gradient(135deg, #4f46e5, #3b82f6);
        color: white;
        padding: 1rem 1.4rem;
        border-radius: 12px;
        margin: 0.8rem auto;
        max-width: 750px;
        font-size: 0.95rem;
        line-height: 1.6;
        box-shadow: 0 4px 12px rgba(79, 70, 229, 0.15);
    }
    .chat-ai {
        background: #ffffff;
        color: #1e293b;
        padding: 1.2rem 1.6rem;
        border-radius: 12px;
        margin: 0.8rem auto;
        max-width: 750px;
        font-size: 0.95rem;
        line-height: 1.6;
        border: 1px solid #e2e8f0;
        border-left: 4px solid #10b981;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
    }

    /* ── Flashcard 3D Flip Card ── */
    .flashcard-deck {
        display: flex;
        flex-wrap: wrap;
        gap: 1.5rem;
        justify-content: center;
        margin: 1.5rem 0;
    }
    .flashcard-container {
        perspective: 1000px;
        width: 320px;
        height: 220px;
    }
    .flip-checkbox {
        display: none;
    }
    .flip-card {
        display: block;
        width: 100%;
        height: 100%;
        cursor: pointer;
        margin: 0;
    }
    .flip-card-inner {
        position: relative;
        width: 100%;
        height: 100%;
        text-align: center;
        transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
        transform-style: preserve-3d;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.05);
        border-radius: 16px;
    }
    .flip-checkbox:checked + .flip-card .flip-card-inner {
        transform: rotateY(180deg);
    }
    .flip-card-front, .flip-card-back {
        position: absolute;
        width: 100%;
        height: 100%;
        -webkit-backface-visibility: hidden;
        backface-visibility: hidden;
        border-radius: 16px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 1.5rem;
        box-sizing: border-box;
    }
    .flip-card-front {
        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
        color: #1e293b;
        border: 1px solid #e2e8f0;
    }
    .flip-card-back {
        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
        color: #065f46;
        transform: rotateY(180deg);
        border: 1px solid #a7f3d0;
    }
    .card-badge {
        font-size: 0.7rem;
        font-weight: 700;
        letter-spacing: 1.5px;
        margin-bottom: 0.8rem;
        text-transform: uppercase;
    }
    .badge-q {
        color: #3b82f6;
        background: #eff6ff;
        padding: 0.2rem 0.6rem;
        border-radius: 10px;
    }
    .badge-a {
        color: #10b981;
        background: #ecfdf5;
        padding: 0.2rem 0.6rem;
        border-radius: 10px;
    }
    .card-text {
        font-size: 1.05rem;
        font-weight: 600;
        line-height: 1.5;
        margin: 0;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    .card-text-back {
        font-size: 0.95rem;
        font-weight: 500;
        line-height: 1.6;
        color: #065f46;
        margin: 0;
    }
    .tap-hint {
        position: absolute;
        bottom: 0.8rem;
        font-size: 0.7rem;
        color: #94a3b8;
        font-style: italic;
    }

    /* ── Sidebar Styling ── */
    .sidebar-section {
        background: linear-gradient(135deg, #f8fafc, #f1f5f9);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #e2e8f0;
    }
    .sidebar-title {
        font-weight: 600;
        color: #1e293b;
        font-size: 0.85rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.5rem;
    }

    /* ── Status badges ── */
    .status-ready {
        display: inline-block;
        background: #dcfce7;
        color: #166534;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }
    .status-waiting {
        display: inline-block;
        background: #fef3c7;
        color: #92400e;
        padding: 0.25rem 0.75rem;
        border-radius: 20px;
        font-size: 0.8rem;
        font-weight: 500;
    }

    /* ── Hide Streamlit defaults ── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* ── Divider ── */
    .styled-divider {
        height: 1px;
        background: linear-gradient(to right, transparent, #cbd5e1, transparent);
        margin: 1rem 0;
        border: none;
    }

    /* ── Setup Screen ── */
    .setup-container {
        max-width: 520px;
        margin: 2rem auto;
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        border-radius: 20px;
        padding: 2.5rem;
        border: 1px solid rgba(99, 102, 241, 0.2);
        box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
    }
    .setup-container h2 {
        color: #ffffff;
        font-size: 1.5rem;
        font-weight: 700;
        margin: 0 0 0.3rem 0;
        text-align: center;
    }
    .setup-container p {
        color: #94a3b8;
        font-size: 0.9rem;
        text-align: center;
        margin: 0 0 1.5rem 0;
        line-height: 1.5;
    }
    .setup-step {
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
        margin: 0.75rem 0;
        color: #cbd5e1;
        font-size: 0.85rem;
        line-height: 1.5;
    }
    .setup-step-num {
        background: linear-gradient(135deg, #6366f1, #3b82f6);
        color: white;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.75rem;
        font-weight: 700;
        flex-shrink: 0;
    }
</style>
""", unsafe_allow_html=True)


# ── Session State Initialization ────────────────────────────────────────────
def init_session_state():
    defaults = {
        "raw_text": None,
        "vector_store": None,
        "chat_history": [],
        "pdf_bytes": None,
        "ppt_bytes": None,
        "audio_bytes": None,
        "audio_script": None,
        "flashcards": None,
        "file_processed": False,
        "file_name": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


init_session_state()


# ── Friendly Error Messages ─────────────────────────────────────────────────
def _friendly_error(e: Exception) -> str:
    """Convert raw exceptions into clean, user-friendly error messages."""
    msg = str(e).lower()
    if "api key not valid" in msg or "api_key_invalid" in msg or "invalid api key" in msg:
        return "Invalid API key. Please check the API key in your .env file and restart the app."
    elif "quota" in msg or "rate limit" in msg or "resource exhausted" in msg:
        return "API quota exceeded. Please wait a moment and try again, or check your billing."
    elif "permission" in msg or "forbidden" in msg:
        return "Access denied. Your API key may not have the required permissions."
    elif "not found" in msg and "model" in msg:
        return "The AI model was not found. Please check your provider configuration."
    elif "connection" in msg or "timeout" in msg or "network" in msg:
        return "Network error. Please check your internet connection and try again."
    else:
        # Keep it concise — first line only
        short = str(e).split('\n')[0]
        if len(short) > 150:
            short = short[:150] + "..."
        return short


# ── Header ──────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📚 AI Study Companion</h1>
    <p>Upload a document, ask questions, and generate study materials — all powered by AI.</p>
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ONE-TIME SETUP SCREEN (only shown when no API key is configured)
# ══════════════════════════════════════════════════════════════════════════════
if not has_key:
    st.markdown("""
    <div class="setup-container">
        <h2>🔐 First-Time Setup</h2>
        <p>Enter your AI API key below to get started. This only needs to be done once — your key will be saved securely on your machine.</p>
        <div class="setup-step">
            <div class="setup-step-num">1</div>
            <div>Get a free API key from <a href="https://aistudio.google.com/apikey" target="_blank" style="color:#818cf8;">Google AI Studio</a> (Gemini) or <a href="https://platform.openai.com/api-keys" target="_blank" style="color:#818cf8;">OpenAI</a></div>
        </div>
        <div class="setup-step">
            <div class="setup-step-num">2</div>
            <div>Paste your key below and click Save</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Setup form
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        setup_provider = st.selectbox(
            "AI Provider",
            options=["gemini", "openai"],
            index=0,
            help="Select which AI provider to use.",
        )
        setup_key = st.text_input(
            f"{'Gemini' if setup_provider == 'gemini' else 'OpenAI'} API Key",
            type="password",
            placeholder="Paste your API key here...",
        )
        if st.button("🚀 Save & Get Started", use_container_width=True, type="primary"):
            if setup_key and setup_key.strip():
                _save_key_to_env(setup_provider, setup_key.strip())
                st.success("✅ API key saved! Restarting app...")
                st.rerun()
            else:
                st.error("Please enter a valid API key.")

    st.stop()  # Don't render the rest of the app until setup is complete


# ══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════════════════
with st.sidebar:
    # ── Status indicator ──
    st.markdown('<span class="status-ready">✓ AI Connected</span>', unsafe_allow_html=True)

    st.markdown('<div class="styled-divider"></div>', unsafe_allow_html=True)

    # ── Study Material Generators ──
    st.markdown("### 🎓 Study Materials")

    doc_ready = st.session_state.file_processed
    disabled = not doc_ready

    if not st.session_state.file_processed:
        st.info("📄 Upload a document to unlock study tools.")

    gen_pdf = st.button(
        "📝 Generate PDF Summary",
        use_container_width=True,
        disabled=disabled,
        help="Create a structured PDF summary of the document.",
    )
    gen_ppt = st.button(
        "📊 Generate PPT Slides",
        use_container_width=True,
        disabled=disabled,
        help="Create a PowerPoint deck with key themes.",
    )
    gen_audio = st.button(
        "🔊 Generate Audio Summary",
        use_container_width=True,
        disabled=disabled,
        help="Create a spoken audio summary you can listen to.",
    )
    gen_flash = st.button(
        "🃏 Generate Flashcards",
        use_container_width=True,
        disabled=disabled,
        help="Create interactive study flashcards.",
    )

    st.markdown('<div class="styled-divider"></div>', unsafe_allow_html=True)

    # ── Document info ──
    if st.session_state.file_processed:
        st.markdown("### 📄 Document Info")
        st.markdown(f"**File:** {st.session_state.file_name}")
        char_count = len(st.session_state.raw_text)
        word_count = len(st.session_state.raw_text.split())
        st.markdown(f"**Words:** {word_count:,}")
        st.markdown(f"**Characters:** {char_count:,}")


# ══════════════════════════════════════════════════════════════════════════════
# FILE UPLOADER
# ══════════════════════════════════════════════════════════════════════════════
if not st.session_state.file_processed:
    st.markdown('<div class="upload-zone">', unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Drop your study material here",
        type=["pdf", "txt"],
        help="Upload a PDF or TXT file to get started.",
        label_visibility="visible",
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if uploaded_file is not None:
        with st.spinner("📖 Reading and indexing your document..."):
            try:
                # Extract text
                raw_text = extract_text(uploaded_file)

                if not raw_text or len(raw_text.strip()) < 50:
                    st.error("❌ The uploaded file appears to be empty or contains very little text.")
                    st.stop()

                # Build vector store
                embeddings = get_embeddings(provider, api_key)
                vector_store = build_vector_store(raw_text, embeddings)

                # Save to session state
                st.session_state.raw_text = raw_text
                st.session_state.vector_store = vector_store
                st.session_state.file_processed = True
                st.session_state.file_name = uploaded_file.name
                st.session_state.chat_history = []

                # Clear any previously generated materials
                st.session_state.pdf_bytes = None
                st.session_state.ppt_bytes = None
                st.session_state.audio_bytes = None
                st.session_state.audio_script = None
                st.session_state.flashcards = None

                st.success("✅ Document indexed successfully! Ask questions below.")
                st.rerun()

            except Exception as e:
                st.error(f"❌ {_friendly_error(e)}")


# ══════════════════════════════════════════════════════════════════════════════
# MAIN CONTENT AREA (after file upload)
# ══════════════════════════════════════════════════════════════════════════════
if st.session_state.file_processed:
    llm = get_llm(provider, api_key)

    # ── Handle sidebar generation buttons ───────────────────────────────────

    # PDF Summary
    if gen_pdf:
        with st.spinner("📝 Generating PDF summary..."):
            try:
                st.session_state.pdf_bytes = generate_pdf_summary(llm, st.session_state.raw_text)
                st.toast("✅ PDF summary ready!", icon="📝")
            except Exception as e:
                st.error(f"❌ PDF generation failed: {_friendly_error(e)}")

    # PPT Slides
    if gen_ppt:
        with st.spinner("📊 Creating presentation slides..."):
            try:
                st.session_state.ppt_bytes = generate_ppt_slides(llm, st.session_state.raw_text)
                st.toast("✅ PPT slides ready!", icon="📊")
            except Exception as e:
                st.error(f"❌ PPT generation failed: {_friendly_error(e)}")

    # Audio Summary
    if gen_audio:
        with st.spinner("🔊 Generating audio summary..."):
            try:
                audio_bytes, script = generate_audio_summary(llm, st.session_state.raw_text)
                st.session_state.audio_bytes = audio_bytes
                st.session_state.audio_script = script
                st.toast("✅ Audio summary ready!", icon="🔊")
            except Exception as e:
                st.error(f"❌ Audio generation failed: {_friendly_error(e)}")

    # Flashcards
    if gen_flash:
        with st.spinner("🃏 Creating flashcards..."):
            try:
                st.session_state.flashcards = generate_flashcards(llm, st.session_state.raw_text)
                st.toast("✅ Flashcards ready!", icon="🃏")
            except Exception as e:
                st.error(f"❌ Flashcard generation failed: {_friendly_error(e)}")

    # ── Chat Section ────────────────────────────────────────────────────────
    st.markdown("## 💬 Ask Questions About Your Document")
    st.markdown('<div class="styled-divider"></div>', unsafe_allow_html=True)

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(f'<div class="chat-user">{msg["content"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="chat-ai">{msg["content"]}</div>', unsafe_allow_html=True)

    # Chat input
    user_question = st.chat_input("Ask a question about your document...")

    if user_question:
        # Add user message
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        # Retrieve relevant chunks
        try:
            docs = st.session_state.vector_store.similarity_search(user_question, k=4)
            context = "\n\n".join([doc.page_content for doc in docs])

            # Build conversation context
            history_text = ""
            for msg in st.session_state.chat_history[-6:]:  # Last 3 exchanges
                role_label = "Student" if msg["role"] == "user" else "AI Tutor"
                history_text += f"{role_label}: {msg['content']}\n"

            rag_prompt = f"""You are a knowledgeable and helpful AI study tutor. Answer the student's 
question accurately based on the provided document context. If the answer cannot be found 
in the context, say so honestly.

Document Context:
{context}

Recent Conversation:
{history_text}

Student's Question: {user_question}

Provide a clear, helpful answer:"""

            response = llm.invoke([HumanMessage(content=rag_prompt)])
            answer = response.content

            # Add AI response
            st.session_state.chat_history.append({"role": "ai", "content": answer})
            st.rerun()

        except Exception as e:
            friendly = _friendly_error(e)
            st.error(f"❌ {friendly}")
            st.session_state.chat_history.append(
                {"role": "ai", "content": f"Sorry, I encountered an error: {friendly}"}
            )

    # ── Generated Materials Display ─────────────────────────────────────────
    has_materials = any([
        st.session_state.pdf_bytes,
        st.session_state.ppt_bytes,
        st.session_state.audio_bytes,
        st.session_state.flashcards,
    ])

    if has_materials:
        st.markdown("---")
        st.markdown("## 📦 Generated Study Materials")

        # --- PDF Summary ---
        if st.session_state.pdf_bytes:
            with st.expander("📝 PDF Summary", expanded=True):
                st.download_button(
                    label="⬇️ Download PDF Summary",
                    data=st.session_state.pdf_bytes,
                    file_name="study_summary.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )

        # --- PPT Slides ---
        if st.session_state.ppt_bytes:
            with st.expander("📊 PowerPoint Slides", expanded=True):
                st.download_button(
                    label="⬇️ Download PPT Slides",
                    data=st.session_state.ppt_bytes,
                    file_name="study_slides.pptx",
                    mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                    use_container_width=True,
                )

        # --- Audio Summary ---
        if st.session_state.audio_bytes:
            with st.expander("🔊 Audio Summary", expanded=True):
                st.audio(st.session_state.audio_bytes, format="audio/mp3")
                if st.session_state.audio_script:
                    st.markdown("**Script:**")
                    st.markdown(f"_{st.session_state.audio_script}_")
                st.download_button(
                    label="⬇️ Download Audio MP3",
                    data=st.session_state.audio_bytes,
                    file_name="study_audio.mp3",
                    mime="audio/mpeg",
                    use_container_width=True,
                )

        # --- Flashcards ---
        if st.session_state.flashcards:
            with st.expander("🃏 Interactive Study Flashcards (Tap to Flip)", expanded=True):
                # We wrap the flashcards inside a self-contained HTML page and render it in an iframe.
                # This completely isolates the HTML and CSS from Streamlit's markdown parser, ensuring
                # perfect 3D flip card rendering with zero raw tags or layout breaks.
                cards_html = """
                <!DOCTYPE html>
                <html>
                <head>
                <style>
                    body {
                        font-family: 'Inter', -apple-system, sans-serif;
                        margin: 0;
                        padding: 10px;
                        background-color: transparent;
                        overflow-x: hidden;
                    }
                    .flashcard-deck {
                        display: flex;
                        flex-wrap: wrap;
                        gap: 1.5rem;
                        justify-content: center;
                        padding: 10px;
                    }
                    .flashcard-container {
                        perspective: 1000px;
                        width: 320px;
                        height: 220px;
                    }
                    .flip-checkbox {
                        display: none;
                    }
                    .flip-card {
                        display: block;
                        width: 100%;
                        height: 100%;
                        cursor: pointer;
                        margin: 0;
                    }
                    .flip-card-inner {
                        position: relative;
                        width: 100%;
                        height: 100%;
                        text-align: center;
                        transition: transform 0.6s cubic-bezier(0.4, 0, 0.2, 1);
                        transform-style: preserve-3d;
                        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.06);
                        border-radius: 16px;
                    }
                    .flip-checkbox:checked + .flip-card .flip-card-inner {
                        transform: rotateY(180deg);
                    }
                    .flip-card-front, .flip-card-back {
                        position: absolute;
                        width: 100%;
                        height: 100%;
                        -webkit-backface-visibility: hidden;
                        backface-visibility: hidden;
                        border-radius: 16px;
                        display: flex;
                        flex-direction: column;
                        align-items: center;
                        justify-content: center;
                        padding: 1.5rem;
                        box-sizing: border-box;
                    }
                    .flip-card-front {
                        background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
                        color: #1e293b;
                        border: 1px solid #e2e8f0;
                    }
                    .flip-card-back {
                        background: linear-gradient(135deg, #ecfdf5 0%, #d1fae5 100%);
                        color: #065f46;
                        transform: rotateY(180deg);
                        border: 1px solid #a7f3d0;
                    }
                    .card-badge {
                        font-size: 0.7rem;
                        font-weight: 700;
                        letter-spacing: 1.5px;
                        margin-bottom: 0.8rem;
                        text-transform: uppercase;
                    }
                    .badge-q {
                        color: #3b82f6;
                        background: #eff6ff;
                        padding: 0.2rem 0.6rem;
                        border-radius: 10px;
                    }
                    .badge-a {
                        color: #10b981;
                        background: #ecfdf5;
                        padding: 0.2rem 0.6rem;
                        border-radius: 10px;
                    }
                    .card-text {
                        font-size: 1.05rem;
                        font-weight: 600;
                        line-height: 1.5;
                        margin: 0;
                        overflow: hidden;
                        text-overflow: ellipsis;
                        color: #1e293b;
                    }
                    .card-text-back {
                        font-size: 0.95rem;
                        font-weight: 500;
                        line-height: 1.6;
                        color: #065f46;
                        margin: 0;
                    }
                    .tap-hint {
                        position: absolute;
                        bottom: 0.8rem;
                        font-size: 0.7rem;
                        color: #94a3b8;
                        font-style: italic;
                    }
                </style>
                </head>
                <body>
                <div class="flashcard-deck">
                """

                for i, card in enumerate(st.session_state.flashcards):
                    q = card['question'].replace('"', '&quot;').replace("'", "&#39;")
                    a = card['answer'].replace('"', '&quot;').replace("'", "&#39;")
                    cards_html += f"""
                    <div class="flashcard-container">
                        <input type="checkbox" id="card-{i}" class="flip-checkbox">
                        <label for="card-{i}" class="flip-card">
                            <div class="flip-card-inner">
                                <div class="flip-card-front">
                                    <span class="card-badge badge-q">❓ Question {i + 1}</span>
                                    <p class="card-text">{q}</p>
                                    <span class="tap-hint">Tap to flip & reveal</span>
                                </div>
                                <div class="flip-card-back">
                                    <span class="card-badge badge-a">💡 Answer {i + 1}</span>
                                    <p class="card-text-back">{a}</p>
                                    <span class="tap-hint">Tap to flip back</span>
                                </div>
                            </div>
                        </label>
                    </div>
                    """

                cards_html += """
                </div>
                </body>
                </html>
                """
                components.html(cards_html, height=520, scrolling=True)

    # ── Reset button ────────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🔄 Upload a Different Document", use_container_width=True):
        for key in [
            "raw_text", "vector_store", "chat_history", "pdf_bytes",
            "ppt_bytes", "audio_bytes", "audio_script", "flashcards",
            "file_processed", "file_name",
        ]:
            st.session_state[key] = None
        st.session_state.chat_history = []
        st.session_state.file_processed = False
        st.rerun()
