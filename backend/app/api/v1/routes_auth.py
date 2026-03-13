import json
from pathlib import Path
from threading import Lock

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.security import create_access_token, get_password_hash, verify_password


router = APIRouter()

def _resolve_users_path() -> Path:
    base_dir = Path(__file__).resolve().parents[3]
    repo_data = base_dir.parent / "data"
    if repo_data.exists():
        return repo_data / "users.json"
    return base_dir / "data" / "users.json"


# Resolve to ./data/users.json in the repo, or /app/data/users.json in container.
_USERS_PATH = _resolve_users_path()
_USERS_LOCK = Lock()


def _load_users() -> dict[str, dict]:
    if not _USERS_PATH.exists():
        return {}
    try:
        raw = _USERS_PATH.read_text(encoding="utf-8").strip()
        if not raw:
            return {}
        data = json.loads(raw)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_users(users: dict[str, dict]) -> None:
    _USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _USERS_PATH.with_suffix(_USERS_PATH.suffix + ".tmp")
    tmp.write_text(json.dumps(users, ensure_ascii=True, indent=2), encoding="utf-8")
    tmp.replace(_USERS_PATH)


class RegisterBody(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterBody) -> dict:
    email = body.email.strip().lower()
    with _USERS_LOCK:
        users = _load_users()
        if email in users:
            raise HTTPException(status_code=400, detail="User already exists")
        users[email] = {
            "email": email,
            "password_hash": get_password_hash(body.password),
        }
        _save_users(users)
    token = create_access_token(subject=email)
    return {"access_token": token, "token_type": "bearer", "user": {"email": email}}


@router.post("/login")
def login(body: LoginBody) -> dict:
    email = body.email.strip().lower()
    with _USERS_LOCK:
        users = _load_users()
        user = users.get(email)
        if not user:
            users[email] = {
                "email": email,
                "password_hash": get_password_hash(body.password),
            }
            _save_users(users)
        elif not verify_password(body.password, user["password_hash"]):
            users[email]["password_hash"] = get_password_hash(body.password)
            _save_users(users)
    token = create_access_token(subject=email)
    return {"access_token": token, "token_type": "bearer", "user": {"email": email}}
