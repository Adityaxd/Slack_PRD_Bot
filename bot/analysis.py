import io
import json
from typing import List, Optional

import pdfplumber
import docx
from openai import OpenAI
from pydantic import BaseModel, Field

from bot.config import Config
import logging

logger = logging.getLogger(__name__)

# Initialize OpenAI client
_llm = OpenAI(api_key=Config.OPENAI_API_KEY)


class Requirement(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    priority: Optional[str] = None  
    assignee: Optional[str] = None
    estimated_hours: Optional[int] = None
    acceptance_criteria: List[str] = Field(default_factory=list)


class RequirementExtractionResponse(BaseModel):
    requirements: List[Requirement]
    document_summary: Optional[str] = None
    total_requirements: int


def extract_text(file_bytes: bytes, filename: str) -> str:
    """
    Extract plain text from PDF, DOCX, or fallback to plain UTF-8 decode.
    """
    ext = filename.rsplit('.', 1)[-1].lower()
    # PDF handling
    if ext == 'pdf':
        text = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
        return '\n'.join(text)

    # DOCX handling
    if ext in ('docx', 'doc'):
        document = docx.Document(io.BytesIO(file_bytes))
        paragraphs = [para.text for para in document.paragraphs if para.text]
        return '\n'.join(paragraphs)

    # Fallback for TXT or other text-based
    try:
        return file_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return ''


def _strip_code_fences(s: str) -> str:
    """
    Remove triple-backtick fences (``` or ```json) from a string.
    """
    lines = s.strip().splitlines()
    if lines and lines[0].startswith("```"):
        # drop first line
        lines = lines[1:]
    if lines and lines[-1].startswith("```"):
        # drop last line
        lines = lines[:-1]
    return "\n".join(lines)


def analyze_with_openai(document_text: str) -> RequirementExtractionResponse:
    """
    Use OpenAI's client API to extract requirements from the document text.
    """
    system_prompt = (
        "You are an expert business analyst. "
        "Extract actionable requirements from the following document. "
        "Return a JSON object with fields: requirements "
        "(array of {id, title, description, priority, assignee, estimated_hours, acceptance_criteria}), "
        "document_summary (brief), and total_requirements (int)."
    )

    response = _llm.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": document_text}
        ],
        temperature=0.1,
    )

    content_raw = response.choices[0].message.content
    if not content_raw:
        raise ValueError("OpenAI response did not contain any content.")

    content = _strip_code_fences(content_raw)

    # parse JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse JSON from model response: %s", e)
        logger.error("Raw model output:\n%s", content_raw)
        raise ValueError(f"Could not parse JSON from model response: {e}")

    return RequirementExtractionResponse(**data)


def analyze_document(file_bytes: bytes, filename: str) -> RequirementExtractionResponse:
    """
    Top-level document analysis entrypoint. Chooses the backend model based on config.
    """
    text = extract_text(file_bytes, filename)
    model = Config.ANALYSIS_MODEL.lower()

    if model == 'openai':
        return analyze_with_openai(text)
    elif model == 'claude':
        raise NotImplementedError("Claude model integration not yet implemented.")
    elif model == 'local':
        raise NotImplementedError("Local model integration not yet implemented.")
    else:
        raise ValueError(f"Unknown ANALYSIS_MODEL: {Config.ANALYSIS_MODEL}")
