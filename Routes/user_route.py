import re

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from Database import pg


router = APIRouter(prefix="/user", tags=["User"])


class UserEmailRequest(BaseModel):
    user_id: str
    email: str


def _validate_user_id(user_id: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_\-]+", user_id):
        raise HTTPException(status_code=400, detail="Invalid user_id")
    return user_id


def _validate_email(email: str) -> str:
    normalized = email.strip().lower()
    if not normalized:
        raise HTTPException(status_code=400, detail="Email is required")

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise HTTPException(status_code=400, detail="Invalid email format")

    return normalized


@router.post("/email")
async def save_user_email(req: UserEmailRequest):
    safe_user_id = _validate_user_id(req.user_id)
    normalized_email = _validate_email(req.email)

    pg.upsert_user_email(safe_user_id, normalized_email)

    return {
        "ok": True,
        "user_id": safe_user_id,
        "email": normalized_email,
        "saved_to": "postgres:user_profiles",
    }


@router.get("/email/{user_id}")
async def get_user_email(user_id: str):
    safe_user_id = _validate_user_id(user_id)
    email = pg.get_user_email(safe_user_id)

    return {
        "ok": True,
        "user_id": safe_user_id,
        "email": email,
    }
