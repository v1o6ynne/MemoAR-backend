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


@router.get("/capture-survey-stats/{user_id}")
async def get_capture_survey_stats(user_id: str):
    safe_user_id = _validate_user_id(user_id)
    try:
        return {
            "ok": True,
            "user_id": safe_user_id,
            "stats": pg.capture_survey_stats(safe_user_id),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read capture survey stats: {e}")


@router.get("/notification-records/{user_id}")
async def get_notification_records(user_id: str, limit: int = 200):
    safe_user_id = _validate_user_id(user_id)
    bounded_limit = max(1, min(limit, 500))

    try:
        return {
            "ok": True,
            "user_id": safe_user_id,
            "records": pg.list_notification_records(safe_user_id, limit=bounded_limit),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read notification records: {e}")


@router.get("/notification-record/{record_id}")
async def get_notification_record(record_id: str):
    safe_record_id = str(record_id).strip()
    if not safe_record_id:
        raise HTTPException(status_code=400, detail="record_id is required")

    try:
        record = pg.get_notification_record(safe_record_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read notification record: {e}")

    if not record:
        raise HTTPException(status_code=404, detail="Notification record not found")

    return {
        "ok": True,
        "record": record,
    }
