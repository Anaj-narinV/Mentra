from fastapi import Request
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Base application error. Carries an HTTP status and a safe, user-facing message."""
    status_code = 400
    detail = "Something went wrong."

    def __init__(self, detail: str | None = None):
        self.detail = detail or self.detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    status_code = 404
    detail = "Resource not found."


class UnauthorizedError(AppError):
    status_code = 401
    detail = "Authentication required."


class ForbiddenError(AppError):
    status_code = 403
    detail = "You don't have access to this resource."


class ConflictError(AppError):
    status_code = 409
    detail = "This resource already exists."


class ValidationAppError(AppError):
    status_code = 422
    detail = "Invalid request data."


class AIUnavailableError(AppError):
    status_code = 503
    detail = "Mentra's AI assistant is temporarily unavailable. Please try again shortly."


async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


async def unhandled_error_handler(request: Request, exc: Exception):
    # Never leak internal exception details to the client.
    return JSONResponse(status_code=500, content={"detail": "Internal server error."})
