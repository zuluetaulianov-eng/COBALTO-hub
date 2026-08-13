"""
models/intel_models.py — Pydantic v2 schemas for static_intel.json validation.

Provides strict typing and validation for OWN_POSTS and NOTES_INFORMATIVAS
so that malformed entries are caught at load time, not silently corrupted.
"""
from __future__ import annotations

import logging
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger("cobalto.models.intel")

# ── Severity levels ──────────────────────────────────────────────────────────
SeverityLevel = Literal["info", "atencion", "urgente", "critico"]


class OwnPost(BaseModel):
    """
    Represents a COBALTO-authored intelligence post.
    These appear in the dashboard as 'own posts' with priority display.
    """

    title: str = Field(..., min_length=3, max_length=500, description="Headline of the post")
    comment_short: str = Field(..., min_length=3, max_length=300, description="Short summary (shown in cards)")
    comment: str = Field(default="", description="Full text of the post")
    source: str = Field(default="COBALTO INTEL", description="Attribution source")
    published: str = Field(default="", description="ISO 8601 datetime string")
    link: str = Field(default="", description="Reference URL (optional)")
    tags: List[str] = Field(default_factory=list, description="Classification tags")
    severity: SeverityLevel = Field(default="info", description="Alert severity level")
    type: str = Field(default="own", description="Entry type identifier (do not change)")

    @field_validator("title", "comment_short", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)

    @field_validator("tags", mode="before")
    @classmethod
    def ensure_list_of_strings(cls, v: object) -> list:
        if v is None:
            return []
        if isinstance(v, list):
            return [str(t) for t in v]
        return []

    @field_validator("link", mode="before")
    @classmethod
    def validate_link(cls, v: object) -> str:
        if not v:
            return ""
        s = str(v).strip()
        if s and not s.startswith(("http://", "https://", "")):
            logger.warning(f"[INTEL MODEL] OwnPost.link tiene esquema no HTTP: '{s}'")
        return s

    @model_validator(mode="after")
    def fill_comment_from_short(self) -> "OwnPost":
        """If comment is empty, use comment_short as the full text."""
        if not self.comment and self.comment_short:
            self.comment = self.comment_short
        return self


class NotaInformativa(BaseModel):
    """
    Represents an editorial/informative note for the dashboard.
    Displayed in the notes panel, not as a main news entry.
    """

    title: str = Field(..., min_length=3, max_length=300, description="Note title")
    body: str = Field(..., min_length=1, description="Note content (HTML or plain text)")
    published: str = Field(default="", description="ISO 8601 datetime string")
    author: str = Field(default="COBALTO", description="Note author")
    pinned: bool = Field(default=False, description="Whether the note is pinned to top")

    @field_validator("title", "body", mode="before")
    @classmethod
    def strip_whitespace(cls, v: object) -> str:
        if isinstance(v, str):
            return v.strip()
        return str(v)


class StaticIntelFile(BaseModel):
    """
    Root schema for the entire static_intel.json file.
    """

    OWN_POSTS: List[OwnPost] = Field(default_factory=list)
    NOTES_INFORMATIVAS: List[NotaInformativa] = Field(default_factory=list)


def load_static_intel(path: str) -> tuple[list[dict], list[dict]]:
    """
    Load and validate static_intel.json with Pydantic schema enforcement.

    Returns:
        (own_posts_dicts, notes_dicts) — validated entries as plain dicts
        for backward compatibility with the rest of the codebase.

    On any error, returns ([], []) and logs the failure — never raises.
    """
    import json
    import os

    if not os.path.exists(path):
        logger.warning(f"[INTEL] static_intel.json no encontrado en: {path}. Usando listas vacías.")
        return [], []

    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"[INTEL] JSON inválido en static_intel.json: {e}. Usando listas vacías.")
        return [], []
    except OSError as e:
        logger.error(f"[INTEL] Error de lectura en static_intel.json: {e}. Usando listas vacías.")
        return [], []

    # Validate with Pydantic — collect errors per item instead of failing all
    own_posts: list[dict] = []
    notes: list[dict] = []

    raw_posts = raw.get("OWN_POSTS", [])
    raw_notes = raw.get("NOTES_INFORMATIVAS", [])

    for i, raw_post in enumerate(raw_posts):
        try:
            post = OwnPost.model_validate(raw_post)
            own_posts.append(post.model_dump())
        except Exception as e:
            logger.warning(f"[INTEL] OWN_POSTS[{i}] inválido — omitido: {e}")

    for i, raw_note in enumerate(raw_notes):
        try:
            note = NotaInformativa.model_validate(raw_note)
            notes.append(note.model_dump())
        except Exception as e:
            logger.warning(f"[INTEL] NOTES_INFORMATIVAS[{i}] inválida — omitida: {e}")

    valid_posts = len(own_posts)
    valid_notes = len(notes)
    skipped_posts = len(raw_posts) - valid_posts
    skipped_notes = len(raw_notes) - valid_notes

    if skipped_posts or skipped_notes:
        logger.warning(
            f"[INTEL] Carga completada con advertencias — "
            f"Posts: {valid_posts} válidos, {skipped_posts} omitidos | "
            f"Notas: {valid_notes} válidas, {skipped_notes} omitidas"
        )
    else:
        logger.info(f"[INTEL] static_intel.json cargado: {valid_posts} posts, {valid_notes} notas")

    return own_posts, notes
