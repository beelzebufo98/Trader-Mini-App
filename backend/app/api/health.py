from fastapi import APIRouter

router = APIRouter()


@router.get("/", summary="Health check")
def health_check() -> dict:
    return {"status": "ok"}
