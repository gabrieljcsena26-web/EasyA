from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/forgot-password")
def forgot_password():
    raise HTTPException(status_code=501, detail="Forgot/reset password disabled in demo")


@router.post("/reset-password")
def reset_password():
    raise HTTPException(status_code=501, detail="Forgot/reset password disabled in demo")
