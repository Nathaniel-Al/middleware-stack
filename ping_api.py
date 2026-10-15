import math
import os
import threading
import time
import uuid
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

ALLOWED_ORIGIN = "https://app-zplzmx.example.com"
RATE_LIMIT = 15          # B requests ...
WINDOW_SECONDS = 10      # ... per 10 seconds

# Your logged-in email, and the exam page's origin (comma-separated if several).
EMAIL = os.getenv("EMAIL")
EXTRA_ORIGINS = [o.strip() for o in os.getenv("EXTRA_ORIGINS", "").split(",") if o.strip()]

if not EMAIL:
    raise RuntimeError("Set the EMAIL environment variable to your logged-in address")

app = FastAPI(title="Ping API")

# ---------------- Middleware 3: per-client rate limiter (innermost) ----------------
HITS: dict[str, deque] = defaultdict(deque)
RL_LOCK = threading.Lock()


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    client_id = request.headers.get("x-client-id") or f"ip:{request.client.host if request.client else 'unknown'}"
    now = time.monotonic()
    with RL_LOCK:
        q = HITS[client_id]
        while q and now - q[0] >= WINDOW_SECONDS:
            q.popleft()
        if len(q) >= RATE_LIMIT:
            retry_after = max(1, math.ceil(WINDOW_SECONDS - (now - q[0])))
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "rate limit exceeded",
                    "request_id": getattr(request.state, "request_id", None),
                },
                headers={"Retry-After": str(retry_after)},
            )
        q.append(now)
    return await call_next(request)


# ---------------- Middleware 1: request context ----------------
@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = (request.headers.get("x-request-id") or "").strip() or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# ---------------- Middleware 2: scoped CORS (outermost) ----------------
# Added last so it wraps everything: preflights are answered here, and
# 429 responses still carry the CORS headers.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN, *EXTRA_ORIGINS],   # explicit list, never "*"
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["X-Request-ID", "X-Client-Id", "Content-Type"],
    expose_headers=["X-Request-ID", "Retry-After"],
)


@app.get("/ping")
async def ping(request: Request):
    return {"email": EMAIL, "request_id": request.state.request_id}


@app.get("/health")
async def health():
    return {"ok": True}
