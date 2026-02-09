"""ASGI entrypoint.

This repository historically had two FastAPI apps:
- `Backend/main.py` (used by `uvicorn main:app` in Docker/systemd)
- `Backend/app/main.py` (the actual app wiring + production hardening)

To keep deployment commands stable, we expose the hardened app here.
"""

from app.main import app  # noqa: F401

__all__ = ["app"]
