export interface ImagenAnexo {
  url: string;
  descripcion?: string;
}

export interface NovedadPatrullaje {
  id: number;
  fecha: string;
  urlPortal: string;
  textoSituacion: string;
  imagenUrl: string;
  imagenDesc: string;
}

export interface OsintEntry {
  id: number;
  tag: string;
  titulo: string;
  fecha: string;
  urlPortal: string;
  textoSituacion: string;
  imagenUrl: string;
  imagenDesc: string;
}

export interface ReporteRequest {
  novedades: {
    fecha_situacion: string;
    portal_web_url: string;
    texto_situacion: string;
    imagenes: { url: string; descripcion?: string }[];
  }[];
}

export interface AnalisisIA {
  actores: string[];
  amenaza: string;
  analisis: string;
}

export interface GenerarWordRequest {
  novedades: ReporteRequest['novedades'];
  analisis_por_novedad: AnalisisIA[];
}
