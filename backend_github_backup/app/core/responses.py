from typing import Any, Optional
from fastapi import HTTPException, status


def success_response(
    data: Optional[Any] = None,
    message: str = "Success"
):
    return {
        "success": True,
        "data": data,
        "message": message
    }


def error_response(
    code: str,
    message: str,
    status_code: int = status.HTTP_400_BAD_REQUEST
):
    raise HTTPException(
        status_code=status_code,
        detail={
            "success": False,
            "error": {
                "code": code,
                "message": message
            }
        }
    )
