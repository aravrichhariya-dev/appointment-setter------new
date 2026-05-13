"""
FastAPI application — mounts all HVAC appointment tool routes.

Run locally:
    uvicorn tools.server:app --port 8001 --reload

Run in production (DigitalOcean, same droplet as n8n):
    uvicorn tools.server:app --host 127.0.0.1 --port 8001
    # Do NOT expose port 8001 publicly — n8n calls FastAPI on localhost internally
"""

import hmac
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import Response
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from tools.book_slot import router as book_router
from tools.call_results import router as call_results_router
from tools.cancel_slot import router as cancel_router
from tools.get_customer import router as get_customer_router
from tools.get_slots import router as get_slots_router
from tools.limiter import limiter
from tools.update_slot import router as update_router

load_dotenv()
_API_SECRET = os.getenv("API_SECRET", "")
if not _API_SECRET:
    raise RuntimeError("API_SECRET is not set in .env — refusing to start")

_MAX_BODY_BYTES = 1_000_000  # 1 MB


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > _MAX_BODY_BYTES:
            return Response("Request body too large", status_code=413)
        return await call_next(request)


async def verify_api_key(x_api_key: str = Header(default="")):
    if not hmac.compare_digest(x_api_key.encode(), _API_SECRET.encode()):
        raise HTTPException(status_code=401, detail="Unauthorized")


app = FastAPI(title="HVAC Appointment API", dependencies=[Depends(verify_api_key)])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(BodySizeLimitMiddleware)

app.include_router(get_customer_router)
app.include_router(get_slots_router)
app.include_router(book_router)
app.include_router(update_router)
app.include_router(cancel_router)
app.include_router(call_results_router)


@app.get("/health")
async def health():
    return {"status": "ok"}
