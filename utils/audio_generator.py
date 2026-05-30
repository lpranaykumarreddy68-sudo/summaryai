"""
Audio Summary Generator — Produces a comprehensive conversational MP3 summary via LLM + gTTS.
"""

import io
from gtts import gTTS
from langchain_core.messages import HumanMessage


AUDIO_PROMPT = """You are a friendly and expert study narrator. Read the following document in its entirety 
and create a highly detailed, comprehensive conversational review script that systematically explains 
the entire file and its contents, including all major concepts, sections, and findings.

Requirements:
- Write a thorough and rich spoken review script (4-6 detailed paragraphs, roughly 350-500 words).
- Begin with a friendly introduction explaining what the document is about overall.
- Walk through each of the main sections, themes, or core concepts in detail.
- Summarize the key takeaways and final conclusions at the end.
- Use a warm, engaging, educational, and conversational tone (as if teaching a student).
- Avoid jargon, special characters, bullet points, asterisks, or markdown formatting — output ONLY plain spoken paragraphs.

Document text:
{text}

Comprehensive Audio Script:"""


def generate_audio_summary(llm, text: str) -> bytes:
    """
    Generate a comprehensive spoken audio summary of the document.

    Args:
        llm: A LangChain chat model.
        text: The full document text.

    Returns:
        MP3 audio file contents as bytes, and the script text.
    """
    # Accept a much larger text window to ensure we cover the entire document
    truncated = text[:40000] if len(text) > 40000 else text
    prompt = AUDIO_PROMPT.format(text=truncated)
    response = llm.invoke([HumanMessage(content=prompt)])
    script = response.content.strip()

    # Convert text to speech
    tts = gTTS(text=script, lang="en", slow=False)
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    return buffer.read(), script
