from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from string import Template
import json
from typing import Optional

from Prompts.memory_prompt import MEMORY_LABEL_EXTRACT_PROMPT, MEMORY_PALETTE_EXTRACT_PROMPT,  NANOBANANA_STYLIZE_PROMPT
from Database import pg
from Memories.gemini_services import GeminiService


router = APIRouter(prefix="/Memory", tags=["Memory"])
LABEL_DB_TEMPLATE = "Database/${PARTICIPANT}/memory_label.json"


class MemoryLabelRequest(BaseModel):
    description: str
    timestamp: Optional[str] = None
    location: Optional[str] = None
    participant: str


@router.post("/label")
async def label_memory(req: MemoryLabelRequest):
    existing_labels_text = pg.get_label_db_text(req.participant)

    prompt = Template(MEMORY_LABEL_EXTRACT_PROMPT).substitute(
        DESCRIPTION=req.description,
        TIMESTAMP=req.timestamp or "",
        LOCATION=req.location or "",
        MEMORY_LABELS=existing_labels_text
    )

    llm = GeminiService()
    raw = llm.complete(prompt)

    try:
        return json.loads(raw)
    except Exception:
        return {
            "error": "Model output is not valid JSON",
            "raw_output": raw
        }


@router.post("/palette")
async def extract_palette(
    image: UploadFile = File(...),
    description: str = Form(...)
):
    llm = GeminiService()

    image_bytes = await image.read()

    prompt = Template(MEMORY_PALETTE_EXTRACT_PROMPT).substitute(
        DESCRIPTION=description
    )

    raw = llm.complete_with_image_bytes(
        prompt=prompt,
        image_bytes=image_bytes,
        mime_type=image.content_type or "image/jpeg"
    )

    try:
        return json.loads(raw)
    except Exception:
        return {
            "error": "Model output is not valid JSON",
            "raw_output": raw
        }
