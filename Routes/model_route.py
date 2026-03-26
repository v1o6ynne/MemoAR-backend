from fastapi import APIRouter, UploadFile, File, Form
from pydantic import BaseModel
from string import Template
import json
from typing import Optional

import os, shutil

from ARItems.tripo_services import (
    generate_model_from_image,
    
)

from Memories.gemini_services import GeminiService
from Prompts.memory_prompt import  NANOBANANA_STYLIZE_PROMPT
from Routes.write_file_route import mark_memory_has_model

router = APIRouter(prefix="/model", tags=["Model"])


class ImageToModelRequest(BaseModel):
    image_path: str
    output_usdz_path: str
    user_id: str
    memory_id: str


@router.post("/image")
async def image_model(req: ImageToModelRequest):
    file_name = os.path.basename(req.output_usdz_path)
    
    supabase_url = await generate_model_from_image(
        image_path=req.image_path,
        user_id=req.user_id,
        file_name=file_name
    )
    
    updated_memory = mark_memory_has_model(
        user_id=req.user_id,
        memory_id=req.memory_id,
        saved_path=supabase_url,
    )
    
    return {
        "saved_path": supabase_url,
        "hasModel": True,
        "memory": updated_memory,
    }



@router.post("/stylize")
async def stylize_model(
    modelImagePath: str = Form(...),
    description: str = Form(...),
    entity: str = Form(...),
    entity_color: str = Form(...),
    file: UploadFile = File(...),
):
    llm = GeminiService()

    image_bytes = await file.read()

    print("===== stylize request =====")
    print("modelImagePath =", modelImagePath)
    print("description =", description)
    print("entity =", entity)
    print("entity_color =", entity_color)
    print("file.filename =", file.filename)
    print("file.content_type =", file.content_type)
    print("image_bytes len =", len(image_bytes))

    if not image_bytes:
        raise ValueError("Uploaded file is empty")


    prompt = Template(NANOBANANA_STYLIZE_PROMPT).substitute(
        DESCRIPTION=description,
        ENTITY=entity,
        ENTITY_COLOR=entity_color,
    )


    reference_image_path = "Reference/reference.png"

    supabase_url = llm.stylize_with_reference(
            prompt=prompt,
            user_image_bytes=image_bytes,
            user_mime_type=file.content_type or "image/jpeg",
            output_path=os.path.basename(modelImagePath),
            reference_image_path=reference_image_path,
        )
    
    return {
        "saved_path": supabase_url,
    }
