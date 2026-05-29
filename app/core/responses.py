from typing import Any

from fastapi import HTTPException
from fastapi.responses import JSONResponse


def success_response(data: Any = None, message: str = "요청이 성공했습니다.") -> dict:
    return {"success": True, "data": data, "message": message}


def error_response(code: str, message: str, status_code: int = 400, details: Any = None) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {"code": code, "message": message, "details": details or {}},
        },
    )


class AppError(HTTPException):
    def __init__(self, code: str, message: str, status_code: int = 400):
        self.error_code = code
        super().__init__(status_code=status_code, detail={"code": code, "message": message})
