"""Punto de entrada: `uv run python -m uvicorn app.main:app --reload`."""

from __future__ import annotations

from app.fabrica import crear_app

app = crear_app()
