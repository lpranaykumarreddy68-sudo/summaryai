"""
Flashcard Generator — Produces interactive study flashcards via LLM.
"""

import json
import re
from langchain_core.messages import HumanMessage


FLASHCARD_PROMPT = """You are an expert educator. Read the following document and create 
exactly 5 high-quality study flashcards that test understanding of the key concepts.

Return your response as a valid JSON array with exactly 5 objects. Each object must have:
- "question": A clear, specific question testing a key concept
- "answer": A concise but complete answer (1-3 sentences)

Example format:
[
  {{"question": "What is X?", "answer": "X is..."}},
  {{"question": "How does Y work?", "answer": "Y works by..."}}
]

IMPORTANT: Return ONLY the JSON array. No markdown, no code fences, no extra text.

Document text:
{text}"""


def _parse_flashcards_json(raw: str) -> list:
    """Parse flashcard JSON from LLM response, handling common formatting issues."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        # Try to find JSON array in the response
        match = re.search(r"\[.*\]", cleaned, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(
                f"Could not parse flashcard JSON from LLM response.\n\nRaw output:\n{raw[:500]}"
            )

    if not isinstance(data, list) or len(data) == 0:
        raise ValueError("Expected a non-empty JSON array of flashcard objects.")

    # Validate structure
    for i, card in enumerate(data):
        if "question" not in card or "answer" not in card:
            raise ValueError(f"Flashcard {i + 1} is missing 'question' or 'answer' keys.")

    return data


def generate_flashcards(llm, text: str) -> list:
    """
    Generate study flashcards from the document.

    Args:
        llm: A LangChain chat model.
        text: The full document text.

    Returns:
        A list of dicts, each with 'question' and 'answer' keys.
    """
    truncated = text[:15000] if len(text) > 15000 else text
    prompt = FLASHCARD_PROMPT.format(text=truncated)

    # First attempt
    response = llm.invoke([HumanMessage(content=prompt)])

    try:
        return _parse_flashcards_json(response.content)
    except (ValueError, json.JSONDecodeError):
        # Retry with stricter instructions
        retry_prompt = (
            "Your previous response was not valid JSON. "
            "Please return ONLY a raw JSON array of 5 flashcard objects, "
            "each with 'question' and 'answer' string fields. "
            "No markdown, no backticks, no explanation. Just the JSON array.\n\n"
            f"Document text:\n{truncated[:8000]}"
        )
        retry_response = llm.invoke([HumanMessage(content=retry_prompt)])
        return _parse_flashcards_json(retry_response.content)
