"""
PDF Summary Generator — Produces a structured PDF summary via LLM + fpdf2.
"""

import io
from fpdf import FPDF
from langchain_core.messages import HumanMessage


SUMMARY_PROMPT = """You are an expert study assistant. Read the following document text and produce 
a comprehensive, well-structured summary suitable for student revision.

Requirements:
- Use clear section headings (prefixed with ##).
- Under each heading, use concise bullet points (prefixed with •).
- Cover ALL core concepts, definitions, and key takeaways.
- Keep language simple and student-friendly.

Document text:
{text}

Structured Summary:"""


def sanitize_latin1(text: str) -> str:
    """
    Sanitize text to make sure it contains only characters supported by Helvetica/Latin-1 in fpdf2.
    Replaces non-Latin-1 characters with standard ASCII equivalents.
    """
    replacements = {
        "\u2022": "-",        # Bullet character (•) -> hyphen
        "\u2013": "-",        # En-dash (–) -> hyphen
        "\u2014": "--",       # Em-dash (—) -> double hyphen
        "\u2018": "'",        # Left single quote (‘) -> straight quote
        "\u2019": "'",        # Right single quote (’) -> straight quote
        "\u201c": '"',        # Left double quote (“) -> straight quote
        "\u201d": '"',        # Right double quote (”) -> straight quote
        "\u2026": "...",      # Ellipsis (…) -> three dots
        "\u00ae": "(R)",      # Registered symbol (®)
        "\u00ad": "",         # Soft hyphen
        "\u2122": "TM",       # Trademark
    }
    
    for uni, ascii_val in replacements.items():
        text = text.replace(uni, ascii_val)
        
    # Force encode as latin-1, replacing any remaining unsupported characters with a safe placeholder "?"
    encoded = text.encode("latin-1", errors="replace")
    return encoded.decode("latin-1")


def generate_pdf_summary(llm, text: str) -> bytes:
    """
    Generate a structured summary of the document and write it to a PDF.

    Args:
        llm: A LangChain chat model.
        text: The full document text.

    Returns:
        PDF file contents as bytes.
    """
    # Truncate very long texts to avoid token limits
    truncated = text[:15000] if len(text) > 15000 else text
    prompt = SUMMARY_PROMPT.format(text=truncated)
    response = llm.invoke([HumanMessage(content=prompt)])
    summary_text = response.content

    # Sanitize the full LLM output to prevent Helvetica encoding failures
    summary_text = sanitize_latin1(summary_text)

    # Build the PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # Title
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(30, 58, 138)  # Dark blue
    pdf.cell(0, 12, "AI Study Companion", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(0, 8, "Document Summary", new_x="LMARGIN", new_y="NEXT", align="C")

    pdf.ln(6)
    pdf.set_draw_color(30, 58, 138)
    pdf.line(15, pdf.get_y(), 195, pdf.get_y())
    pdf.ln(8)

    # Body
    pdf.set_text_color(30, 30, 30)
    for line in summary_text.split("\n"):
        line = line.strip()
        if not line:
            pdf.ln(3)
            continue

        if line.startswith("##"):
            pdf.ln(4)
            pdf.set_font("Helvetica", "B", 13)
            pdf.set_text_color(30, 58, 138)
            pdf.multi_cell(0, 7, line.replace("##", "").strip())
            pdf.ln(2)
        elif line.startswith(("•", "-", "*")):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            # Clean up the bullet
            clean = line.lstrip("•-* ").strip()
            # Use standard hyphen bullet to avoid Latin-1 encoding errors
            pdf.multi_cell(0, 6, f"  -  {clean}")
            pdf.ln(1)
        else:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            pdf.multi_cell(0, 6, line)
            pdf.ln(1)

    # Return as bytes
    buffer = io.BytesIO()
    pdf.output(buffer)
    buffer.seek(0)
    return buffer.read()
