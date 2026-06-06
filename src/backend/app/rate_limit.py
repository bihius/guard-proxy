"""Rate-limiting primitives for Guard Proxy.

Uses slowapi (backed by limits, in-memory MemoryStorage) — appropriate for a
single-process uvicorn deployment.  The limiter is instantiated here so it can
be imported by both main.py (registration) and any router that needs a decorator.

IP resolution
-------------
HAProxy sits in front of the backend and stamps ``X-Forwarded-For`` with the
real source IP (``http-request set-header X-Forwarded-For %[src]`` in
haproxy.cfg), overwriting any value the client may have injected.  We therefore
trust the first entry of the XFF header when it is present and fall back to the
socket peer address otherwise (direct connections in dev / tests).
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def client_ip(request: Request) -> str:
    """Return the real client IP to use as the rate-limit key.

    HAProxy sets ``X-Forwarded-For: <real-src-ip>`` before forwarding to
    uvicorn, so the first (and only) entry is the canonical client address.
    If the header is absent (direct connection in dev or tests) we fall back
    to the socket peer returned by slowapi's built-in helper.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return get_remote_address(request)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return a 429 in the API-standard ``{"detail": ...}`` shape.

    The whole API and the frontend ``api-client.ts`` expect a ``detail`` key.
    Using the same shape here ensures the login form can surface a meaningful
    error message rather than the generic "Request failed" fallback.

    ``Retry-After`` is a static 60 s: the limit is a 1-minute fixed window, so
    the worst-case wait never exceeds 60 seconds.
    """
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many requests. Please wait a minute and try again."},
        headers={"Retry-After": "60"},
    )


#: Shared limiter instance.  Register with the FastAPI app via:
#:   app.state.limiter = limiter
#:   app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
limiter = Limiter(key_func=client_ip)

#: Brute-force limit applied to auth endpoints that accept credentials.
AUTH_RATE_LIMIT = "5/minute"
