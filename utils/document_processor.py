"""
Document Processor — PDF/TXT text extraction and FAISS vector store indexing.
"""

import io
from pypdf import PdfReader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS


def extract_text(uploaded_file) -> str:
    """
    Extract raw text from an uploaded PDF or TXT file.
    Returns the full document text as a single string.
    """
    filename = uploaded_file.name.lower()

    if filename.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(uploaded_file.read()))
        pages = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                pages.append(text)
        return "\n\n".join(pages)

    elif filename.endswith(".txt"):
        return uploaded_file.read().decode("utf-8", errors="replace")

    else:
        raise ValueError(f"Unsupported file type: {filename}. Please upload a PDF or TXT file.")


def build_vector_store(text: str, embeddings) -> FAISS:
    """
    Split text into chunks and build an in-memory FAISS vector store.

    Args:
        text: The full document text.
        embeddings: A LangChain embeddings instance (Gemini or OpenAI).

    Returns:
        A FAISS vector store ready for similarity search.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.create_documents([text])

    if not chunks:
        raise ValueError("No text chunks could be created from the document.")

    vector_store = FAISS.from_documents(chunks, embeddings)
    return vector_store
