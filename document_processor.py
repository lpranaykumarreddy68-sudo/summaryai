"""
Document Processor — Extractor and FAISS disk-based Vector Store indexer.
Extracts text from PDF/TXT files and manages FAISS indexes stored on disk for memory protection.
"""

import io
import os
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

# Base directory for storing vector indexes locally
IS_VERCEL = os.getenv("VERCEL") == "1"

if IS_VERCEL:
    VECTOR_STORES_DIR = "/tmp/vector_stores"
else:
    STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
    VECTOR_STORES_DIR = os.path.join(STATIC_DIR, "vector_stores")

os.makedirs(VECTOR_STORES_DIR, exist_ok=True)


def extract_text_from_bytes(file_bytes: bytes, filename: str) -> str:
    """
    Extract raw text from file bytes (PDF or TXT).
    """
    filename_lower = filename.lower()
    if filename_lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(file_bytes))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)
    elif filename_lower.endswith(".txt"):
        return file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError(f"Unsupported file type: {filename}. Only PDF and TXT are supported.")


def save_vector_store(session_id: str, text: str, embeddings) -> str:
    """
    Create a FAISS vector store, save it to disk under a unique session_id path,
    and return the save folder path.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.create_documents([text])
    if not chunks:
        raise ValueError("No text chunks could be created from the document.")

    # Build and save index
    vector_store = FAISS.from_documents(chunks, embeddings)
    folder_path = os.path.join(VECTOR_STORES_DIR, session_id)
    os.makedirs(folder_path, exist_ok=True)
    vector_store.save_local(folder_path)
    return folder_path


def load_vector_store(session_id: str, embeddings) -> FAISS:
    """
    Load a FAISS vector store from disk on-demand for a given session.
    """
    folder_path = os.path.join(VECTOR_STORES_DIR, session_id)
    if not os.path.exists(folder_path):
        raise FileNotFoundError(f"Vector store not found for session: {session_id}")
    
    return FAISS.load_local(
        folder_path,
        embeddings,
        allow_dangerous_deserialization=True  # Required by LangChain to load pickled local indices
    )
