from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import re

router = APIRouter(prefix="/readData", tags=["ReadData"])

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_ROOT = (PROJECT_ROOT / "Database").resolve()

def _validate_user_id(user_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    return user_id

@router.get("/memory-list/{user_id}")
async def get_memory_list(user_id: str):
    safe_user_id = _validate_user_id(user_id)
    file_path = (DATABASE_ROOT / safe_user_id / "memory_list.json").resolve()

    print("==== DEBUG memory-list ====")
    print("PROJECT_ROOT =", PROJECT_ROOT)
    print("DATABASE_ROOT =", DATABASE_ROOT)
    print("user_id =", repr(user_id))
    print("safe_user_id =", repr(safe_user_id))
    print("file_path =", file_path)
    print("file_exists =", file_path.exists())

    if not str(file_path).startswith(str(DATABASE_ROOT)):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not file_path.exists():
        print("❌ file not found")
        return {
            "ok": True,
            "memories": [],
            "debug_path": str(file_path)
        }

    try:
        raw = file_path.read_text(encoding="utf-8").strip()
        print("raw length =", len(raw))
        print("raw preview =", raw[:300])

        data = json.loads(raw) if raw else []
        print("parsed count =", len(data))
        print("===========================")

        return {
            "ok": True,
            "memories": data,
            "debug_path": str(file_path)
        }
    except Exception as e:
        print("❌ read error =", repr(e))
        raise HTTPException(status_code=500, detail=f"Failed to read memory list: {e}")