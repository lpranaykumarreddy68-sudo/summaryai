"""
LLM Provider — Abstraction layer for Gemini and OpenAI models.
"""

from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings


def get_llm(provider: str, api_key: str):
    """
    Return a LangChain chat model based on the selected provider.

    Args:
        provider: 'gemini' or 'openai'.
        api_key: The API key for the chosen provider.

    Returns:
        A LangChain chat model instance.
    """
    if provider == "gemini":
        primary = ChatGoogleGenerativeAI(
            model="models/gemini-2.5-flash",
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True,
        )
        fb1 = ChatGoogleGenerativeAI(
            model="models/gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True,
        )
        fb2 = ChatGoogleGenerativeAI(
            model="models/gemini-1.5-flash",
            google_api_key=api_key,
            temperature=0.3,
            convert_system_message_to_human=True,
        )
        return primary.with_fallbacks([fb1, fb2])
    elif provider == "openai":
        return ChatOpenAI(
            model="gpt-4o-mini",
            openai_api_key=api_key,
            temperature=0.3,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}. Use 'gemini' or 'openai'.")


def get_embeddings(provider: str, api_key: str):
    """
    Return a LangChain embeddings model based on the selected provider.

    Args:
        provider: 'gemini' or 'openai'.
        api_key: The API key for the chosen provider.

    Returns:
        A LangChain embeddings instance.
    """
    if provider == "gemini":
        return GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            google_api_key=api_key,
        )
    elif provider == "openai":
        return OpenAIEmbeddings(
            openai_api_key=api_key,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}. Use 'gemini' or 'openai'.")
