from typing import Optional

from pydantic import BaseModel


class OsintEntry(BaseModel):
    id: int
    tag: str
    titulo: str
    fecha: str
    urlPortal: str
    textoSituacion: str
    imagenUrl: str
    imagenDesc: str


class OsintSearchParams(BaseModel):
    tag: Optional[str] = None
    q: Optional[str] = None
    limit: int = 10
    offset: int = 0
