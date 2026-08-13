from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ImagenAnexo(BaseModel):
    url: Optional[HttpUrl] = None
    descripcion: str = Field(default="", max_length=500)


class NovedadPatrullaje(BaseModel):
    fecha_situacion: str = Field(..., max_length=50)
    portal_web_url: HttpUrl
    texto_situacion: str = Field(..., min_length=10, max_length=5000)
    imagenes: List[ImagenAnexo]


class AnalisisIA(BaseModel):
    actores: List[str]
    amenaza: str
    analisis: str


class ReporteRequest(BaseModel):
    novedades: List[NovedadPatrullaje]


class GenerarWordRequest(BaseModel):
    novedades: List[NovedadPatrullaje]
    analisis_por_novedad: List[AnalisisIA]
