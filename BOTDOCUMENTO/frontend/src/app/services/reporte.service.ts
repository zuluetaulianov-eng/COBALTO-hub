import { Injectable, Inject, InjectionToken, Optional } from '@angular/core';
import { HttpClient, HttpErrorResponse, HttpParams, HttpHeaders } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import {
  ReporteRequest,
  GenerarWordRequest,
  AnalisisIA,
  OsintEntry,
} from '../components/cobalto-report/cobalto-report.model';

export const API_BASE_URL = new InjectionToken<string>('API_BASE_URL');

@Injectable({ providedIn: 'root' })
export class ReporteService {
  private _authToken: string | null = null;

  constructor(
    private http: HttpClient,
    @Optional() @Inject(API_BASE_URL) private baseUrl: string | null,
  ) {
    this.baseUrl = baseUrl ?? '';
  }

  setBaseUrl(url: string) {
    this.baseUrl = url;
  }

  setAuthToken(token: string | null) {
    this._authToken = token;
  }

  private _headers(): HttpHeaders {
    if (!this._authToken) return new HttpHeaders();
    return new HttpHeaders({ Authorization: `Bearer ${this._authToken}` });
  }

  private url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  analizarIA(payload: ReporteRequest): Observable<AnalisisIA[]> {
    return this.http
      .post<AnalisisIA[]>(this.url('/api/reportes/analizar-ia'), payload, {
        headers: this._headers(),
      })
      .pipe(catchError((err) => this._handleError(err)));
  }

  generarWord(payload: GenerarWordRequest): Observable<Blob> {
    return this.http
      .post(this.url('/api/reportes/generar-word'), payload, {
        responseType: 'blob',
        headers: this._headers(),
      })
      .pipe(catchError((err) => this._handleError(err)));
  }

  getOsintEntries(params?: {
    tag?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }): Observable<{
    data: OsintEntry[];
    total: number;
    limit: number;
    offset: number;
  }> {
    let httpParams = new HttpParams();
    if (params?.tag) httpParams = httpParams.set('tag', params.tag);
    if (params?.q) httpParams = httpParams.set('q', params.q);
    if (params?.limit) httpParams = httpParams.set('limit', params.limit);
    if (params?.offset) httpParams = httpParams.set('offset', params.offset);
    return this.http.get<{
      data: OsintEntry[];
      total: number;
      limit: number;
      offset: number;
    }>(this.url('/api/osint/entries'), {
      params: httpParams,
      headers: this._headers(),
    });
  }

  getOsintTags(): Observable<string[]> {
    return this.http.get<string[]>(this.url('/api/osint/tags'), {
      headers: this._headers(),
    });
  }

  private async _parseBlobError(error: HttpErrorResponse): Promise<string> {
    if (error.error instanceof Blob) {
      try {
        const text = await error.error.text();
        const parsed = JSON.parse(text);
        return parsed.detail || 'Error del servidor.';
      } catch {
        // not JSON, return generic
      }
    }
    return error.error?.detail || '';
  }

  private _handleError(error: HttpErrorResponse) {
    if (error.status === 401) {
      return throwError(() => new Error('Token de autenticación inválido o expirado.'));
    }

    if (error.status === 422 && error.error instanceof Blob) {
      return new Observable<never>((observer) => {
        this._parseBlobError(error).then(detail => {
          observer.error(new Error(detail || 'Datos inválidos en la solicitud.'));
        });
      });
    }

    let msg = 'Error de conexión con el servidor.';
    if (error.status === 422) {
      msg = error.error?.detail || 'Datos inválidos en la solicitud.';
    } else if (error.status === 504) {
      msg = 'La IA no respondió a tiempo. Intente nuevamente.';
    } else if (error.status === 0) {
      msg = 'No se pudo conectar con el servidor. Verifica que el backend esté corriendo.';
    }
    return throwError(() => new Error(msg));
  }
}
