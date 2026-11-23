"""FastAPI application. Start it with:

    uvicorn app.main:app --reload --port 8081

Then open http://127.0.0.1:8081 for the nurse interface,
or http://127.0.0.1:8081/docs to see and try every endpoint.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.routers import admin, auth, consultations, protocols

log = logging.getLogger("uvicorn.error")

if settings.using_default_secret:
    if settings.environment == "production":
        raise RuntimeError("SECRET_KEY in .env is missing or too short. Set a long random value before running in production.")
    log.warning("SECRET_KEY is the development default. Set a long random SECRET_KEY in .env before real use.")

app = FastAPI(
    title="Nurse Telephone Triage DSS",
    version="0.5.0",
    description="Decision support for nurse telephone triage, using Schmitt-Thompson-style protocols "
                "adapted for Nigerian primary care. MIT Professional Master's Project, Miva Open University.",
)

# ---------------------------------------------------------------- security headers
CSP = ("default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self'; connect-src 'self'; object-src 'none'; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'none'")
DOCS = ("/docs", "/redoc", "/openapi.json")


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    h = response.headers
    h["X-Content-Type-Options"] = "nosniff"
    h["X-Frame-Options"] = "DENY"
    h["Referrer-Policy"] = "no-referrer"
    h["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    if not path.startswith(DOCS):  # the /docs page loads its own scripts from a CDN
        h["Content-Security-Policy"] = CSP
    if not path.startswith("/ui/") and not path.startswith(DOCS):
        h["Cache-Control"] = "no-store"  # health data must not be kept in browser or proxy caches
    if request.url.scheme == "https":
        h["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth.router)
app.include_router(protocols.router)
app.include_router(consultations.router)
app.include_router(admin.router)


STATIC = Path(__file__).resolve().parent / "static"
app.mount("/ui", StaticFiles(directory=STATIC, html=True), name="ui")


@app.get("/", include_in_schema=False)
def home():
    return RedirectResponse("/ui/login.html")


@app.get("/health", tags=["System"], summary="Check the server is running")
def health():
    return {"status": "ok"}
