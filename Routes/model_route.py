

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


# @router.post("/image")
# async def image_model(req: ImageToModelRequest):
#     saved_path = await generate_model_from_image(
#         image_path=req.image_path,
#         output_usdz_path=req.output_usdz_path,
#     )
#     updated_memory = mark_memory_has_model(
#         user_id=req.user_id,
#         memory_id=req.memory_id,
#         saved_path=saved_path,
#     )
#     return {
#         "saved_path": saved_path,
#         "hasModel": True,
#         "memory": updated_memory,
#     }

@router.post("/image")
async def image_model(req: ImageToModelRequest):
    # 1. 调用生成函数。注意：我们不再依赖本地 path，而是让它返回 Supabase URL
    # 我们把 req.output_usdz_path 作为一个逻辑上的文件名传进去即可
    file_name = os.path.basename(req.output_usdz_path) 
    
    supabase_url = await generate_model_from_image(
        image_path=req.image_path,
        user_id=req.user_id, # 传 user_id 方便在 Supabase 建文件夹
        file_name=file_name
    )
    
    # 2. 更新内存记录。现在的 saved_path 是一个 https 链接
    updated_memory = mark_memory_has_model(
        user_id=req.user_id,
        memory_id=req.memory_id,
        saved_path=supabase_url, # 存入数据库的是 URL
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

    # os.makedirs("tmp", exist_ok=True)
    # debug_path = f"tmp/debug_{file.filename or 'upload.jpg'}"
    # with open(debug_path, "wb") as f:
    #     f.write(image_bytes)
    # print("saved debug file to", debug_path)


    prompt = Template(NANOBANANA_STYLIZE_PROMPT).substitute(
        DESCRIPTION=description,
        ENTITY=entity,
        ENTITY_COLOR=entity_color,
    )

    reference_image_path = "Storage/Reference/reference.png"

    # saved_path = llm.stylize_with_reference(
    #     prompt=prompt,
    #     user_image_bytes=image_bytes,
    #     user_mime_type=file.content_type or "image/jpeg",
    #     output_path=modelImagePath,
    #     reference_image_path=reference_image_path,
    # )
    # return {
    #     "saved_path": saved_path,
    # }

    supabase_url = llm.stylize_with_reference(
            prompt=prompt,
            user_image_bytes=image_bytes,
            user_mime_type=file.content_type or "image/jpeg",
            file_name=os.path.basename(modelImagePath),
            reference_image_path=reference_image_path,
        )
    
    return {
        "saved_path": supabase_url,
    }