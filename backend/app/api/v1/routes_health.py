from fastapi import APIRouter


router = APIRouter()


@router.get("/live")
def liveness() -> dict:
    return {"status": "ok"}


@router.get("/ready")
def readiness() -> dict:
    # In a full implementation we would check DB, Redis, external APIs, etc.
    return {"status": "ready"}

