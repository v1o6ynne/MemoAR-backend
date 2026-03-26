from fastapi import APIRouter, HTTPException
from pathlib import Path
import json
import re
from Database import pg

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
    try:
        memories = pg.list_memories(safe_user_id, limit=200)
        return {
            "ok": True,
            "memories": memories,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read memory list (postgres): {e}")
