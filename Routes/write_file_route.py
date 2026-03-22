from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json
import re

router = APIRouter(prefix="/writeData", tags=["WriteData"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STORAGE_ROOT = (PROJECT_ROOT / "Storage").resolve()
DATABASE_ROOT = (PROJECT_ROOT / "Database").resolve()


@router.post("/upload-user-image")
async def upload_user_image(
    relative_path: str = Form(...),
    image: UploadFile = File(...),
):
    rel = Path(relative_path)

    if rel.is_absolute() or ".." in rel.parts:
        raise HTTPException(status_code=400, detail="Invalid path")

    save_path = (PROJECT_ROOT / rel).resolve()

    if not str(save_path).startswith(str(STORAGE_ROOT)):
        raise HTTPException(status_code=400, detail="Path must be inside Storage")

    if not image.content_type or not image.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Uploaded file must be an image")

    save_path.parent.mkdir(parents=True, exist_ok=True)

    contents = await image.read()
    save_path.write_bytes(contents)

    return {"ok": True}


class UpsertMemoryRequest(BaseModel):
    user_id: str
    memory: dict


def _validate_user_id(user_id: str) -> str:
    # 只允许类似 P01 / user123 / abc_def 这种
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    return user_id


def _memory_list_path(user_id: str) -> Path:
    safe_user_id = _validate_user_id(user_id)
    user_dir = (DATABASE_ROOT / safe_user_id).resolve()

    if not str(user_dir).startswith(str(DATABASE_ROOT)):
        raise HTTPException(status_code=400, detail="Invalid database path")

    user_dir.mkdir(parents=True, exist_ok=True)
    return user_dir / "memory_list.json"


def _load_memory_list(path: Path) -> list:
    if not path.exists():
        return []

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to read memory_list.json")


def _atomic_write_json(path: Path, data: list):
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    tmp_path.replace(path)


@router.post("/upsert-memory")
async def upsert_memory(req: UpsertMemoryRequest):
    memory = req.memory
    user_id = req.user_id

    memory_id = memory.get("id")
    if not memory_id:
        raise HTTPException(status_code=400, detail="memory.id is required")

    file_path = _memory_list_path(user_id)
    memory_list = _load_memory_list(file_path)

    existing_index = next(
        (i for i, item in enumerate(memory_list) if item.get("id") == memory_id),
        None
    )

    if existing_index is not None:
        memory_list[existing_index] = memory
    else:
        memory_list.insert(0, memory)

    # 可选：最多保留 100 条
    # memory_list = memory_list[:100]

    _atomic_write_json(file_path, memory_list)

    return {
        "ok": True,
        "user_id": user_id,
        "memory_id": memory_id,
        "count": len(memory_list),
        "saved_to": str(file_path.relative_to(PROJECT_ROOT))
    }


def mark_memory_has_model(user_id: str, memory_id: str, saved_path: str):
    file_path = _memory_list_path(user_id)
    memory_list = _load_memory_list(file_path)

    existing_index = next(
        (i for i, item in enumerate(memory_list) if item.get("id") == memory_id),
        None
    )

    if existing_index is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    memory_list[existing_index]["arPath"] = saved_path
    memory_list[existing_index]["hasModel"] = True

    _atomic_write_json(file_path, memory_list)

    return memory_list[existing_index]