"""Rate-limiting primitives for Guard Proxy.

Uses slowapi (backed by limits, in-memory MemoryStorage) — appropriate for a
single-process uvicorn deployment.  The limiter is instantiated here so it can
be imported by both main.py (registration) and any router that needs a decorator.

IP resolution
-------------
HAProxy sits in front of the backend and stamps ``X-Forwarded-For`` with the
real source IP (``http-request set-header X-Forwarded-For %[src]`` in
haproxy.cfg), replacing any value the client may have injected.  The UI proxy
in front of the backend appends what it received instead (Vite ``xfwd``, nginx
``$proxy_add_x_forwarded_for``), so the right-most entry is the address the
nearest proxy observed.  That entry is used when the header is present, and the
socket peer address otherwise (direct connections in dev / tests).
"""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def client_ip(request: Request) -> str:
    """Return the real client IP to use as the rate-limit key.

    Each proxy appends the address it received the connection from, so the
    right-most entry of ``X-Forwarded-For`` is the one the closest proxy added:
    HAProxy replaces the header with the real source IP, and the UI proxy
    appends its peer.  Trusting the left-most entry instead gave every request a
    fresh bucket whenever a proxy appends rather than replaces, because the
    client can prepend arbitrary values.  If the header is absent (direct
    connection in dev or tests) the socket peer is used.
    """
    xff = request.headers.get("x-forwarded-for")
    if xff:
        entry = xff.split(",")[-1].strip()
        if entry:
            return entry
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

#: Brute-force limit applied to auth endpoints that accept credentials
#: (login). Deliberately strict because each attempt is a password guess.
AUTH_RATE_LIMIT = "5/minute"

#: Limit applied to the token-refresh endpoint. Refresh carries no
#: user-supplied credentials — only a signed, HttpOnly refresh cookie — and the
#: frontend calls it automatically on every page load (twice under React
#: StrictMode in dev). The strict login limit would therefore reject normal
#: reloads with a 429 and bounce the user to the login page, so refresh gets a
#: much more generous ceiling that still bounds abuse of the rotating-token
#: endpoint.
REFRESH_RATE_LIMIT = "60/minute"
