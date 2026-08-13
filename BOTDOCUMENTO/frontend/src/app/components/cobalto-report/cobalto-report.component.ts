import { Component, ChangeDetectionStrategy, signal, Input, inject, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ReporteService } from '../../services/reporte.service';
import { NovedadPatrullaje, OsintEntry, ReporteRequest, AnalisisIA, GenerarWordRequest } from './cobalto-report.model';
import { Lang, I18N } from './cobalto-report.i18n';
import { Subscription, Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';

@Component({
  selector: 'lib-cobalto-report',
  standalone: true,
  imports: [CommonModule, FormsModule],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './cobalto-report.component.html',
  providers: [ReporteService],
})
export class CobaltoReportComponent implements OnInit, OnDestroy {
  @Input() maxNovedades = 2;
  @Input() lang: Lang = 'es';
  @Input() mode: 'full' | 'embed' = 'full';
  @Input() set apiBaseUrl(url: string | undefined) {
    if (url) this.reporteService.setBaseUrl(url);
  }
  @Input() set authToken(token: string | undefined) {
    this.reporteService.setAuthToken(token ?? null);
  }

  get i18n() { return I18N[this.lang]; }
  get isEmbed() { return this.mode === 'embed'; }
  get puedeEnviar(): boolean {
    return this.noticias().some(n => n.textoSituacion.trim().length > 0);
  }

  private reporteService = inject(ReporteService);
  private sub: Subscription | null = null;
  private busquedaSub: Subscription | null = null;
  private busquedaSubject = new Subject<string>();

  osintDatabase = signal<OsintEntry[]>([]);
  osintTotal = signal(0);
  osintLoading = signal(false);
  osintSearchQuery = signal('');
  osintSelectedTag = signal<string | null>(null);
  osintTags = signal<string[]>([]);

  noticias = signal<NovedadPatrullaje[]>([this.noticiaVacia()]);
  fase = signal<'input' | 'preview'>('input');
  analisisGenerado = signal<AnalisisIA[]>([]);

  cargando = signal<boolean>(false);
  progreso = signal(0);
  progresoTexto = signal('');
  mensajeExito = signal<boolean>(false);
  errorMsg = signal<string | null>(null);
  toastMsg = signal<string | null>(null);
  camposInvalidos = signal<Record<string, boolean>>({});

  ngOnInit() {
    this._cargarOsintTags();
    this._cargarOsintEntries();
    this.busquedaSub = this.busquedaSubject.pipe(
      debounceTime(300),
      distinctUntilChanged(),
    ).subscribe(() => this._cargarOsintEntries());
  }

  private noticiaVacia(): NovedadPatrullaje {
    return { id: Date.now(), fecha: '', urlPortal: '', textoSituacion: '', imagenUrl: '', imagenDesc: '' };
  }

  private _cargarOsintTags() {
    this.reporteService.getOsintTags().subscribe({
      next: (tags) => this.osintTags.set(tags),
    });
  }

  private _cargarOsintEntries() {
    this.osintLoading.set(true);
    this.reporteService
      .getOsintEntries({
        tag: this.osintSelectedTag() ?? undefined,
        q: this.osintSearchQuery() || undefined,
        limit: 20,
      })
      .subscribe({
        next: (res) => {
          this.osintDatabase.set(res.data);
          this.osintTotal.set(res.total);
          this.osintLoading.set(false);
        },
        error: () => this.osintLoading.set(false),
      });
  }

  filtrarPorTag(tag: string | null) {
    this.osintSelectedTag.set(tag);
    this._cargarOsintEntries();
  }

  buscarOsint() {
    this.busquedaSubject.next(this.osintSearchQuery());
  }

  private _campoId(index: number, campo: string): string {
    return `novedad-${index}-${campo}`;
  }

  private _validar(): boolean {
    const invalidos: Record<string, boolean> = {};
    this.noticias().forEach((n, i) => {
      if (!n.textoSituacion.trim()) {
        invalidos[this._campoId(i, 'textoSituacion')] = true;
      }
    });
    this.camposInvalidos.set(invalidos);
    return Object.keys(invalidos).length === 0;
  }

  esInvalido(index: number, campo: string): boolean {
    return !!this.camposInvalidos()[this._campoId(index, campo)];
  }

  actualizarNoticia(index: number, campo: keyof NovedadPatrullaje, valor: string) {
    this.noticias.update(lista => {
      const nueva = [...lista];
      nueva[index] = { ...nueva[index], [campo]: valor };
      return nueva;
    });
    if (campo === 'textoSituacion' && valor.trim()) {
      this.camposInvalidos.update(m => {
        const next = { ...m };
        delete next[this._campoId(index, 'textoSituacion')];
        return next;
      });
    }
  }

  agregarNoticiaVacia() {
    if (this.noticias().length < this.maxNovedades) {
      this.noticias.update(lista => [...lista, this.noticiaVacia()]);
      setTimeout(() => {
        const idx = this.noticias().length - 1;
        document.getElementById('fecha-' + idx)?.focus();
      });
    }
  }

  removerNoticia(index: number) {
    const noticia = this.noticias()[index];
    const tieneDatos = noticia.textoSituacion.trim() || noticia.urlPortal.trim() || noticia.fecha.trim();
    if (tieneDatos && !confirm(this.i18n['confirmar_eliminar'])) return;
    this.noticias.update(lista => lista.filter((_, i) => i !== index));
    if (this.noticias().length === 0) this.agregarNoticiaVacia();
  }

  importarDesdeOsint(item: OsintEntry) {
    if (this.noticias().length >= this.maxNovedades) {
      this.toastMsg.set(this.i18n['max_novedades_alerta'].replace('{max}', String(this.maxNovedades)));
      setTimeout(() => this.toastMsg.set(null), 4000);
      return;
    }
    this.noticias.update(lista => {
      const nueva: NovedadPatrullaje = {
        id: Date.now(),
        fecha: item.fecha,
        urlPortal: item.urlPortal,
        textoSituacion: item.textoSituacion,
        imagenUrl: item.imagenUrl,
        imagenDesc: item.imagenDesc,
      };
      const unicaVacia = lista.length === 1 && lista[0].urlPortal === '' && lista[0].textoSituacion === '';
      return unicaVacia ? [nueva] : [...lista, nueva];
    });
    this.toastMsg.set(this.i18n['osint_importada']);
    setTimeout(() => this.toastMsg.set(null), 4000);
  }

  autoResize(event: Event) {
    const ta = event.target as HTMLTextAreaElement;
    ta.style.height = 'auto';
    ta.style.height = ta.scrollHeight + 'px';
  }

  handleImageError(event: Event) {
    (event.target as HTMLImageElement).src =
      'data:image/svg+xml;base64,' + btoa('<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><rect width="100" height="100" fill="#0f172a"/><text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" font-family="sans-serif" font-size="10" fill="#475569">NO DISPONIBLE</text></svg>');
  }

  private _descargarBlob(blob: Blob) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'Reporte_Patrullaje_Cobalto.docx';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  iniciarAnalisis() {
    if (!this._validar()) return;
    this.cargando.set(true);
    this.mensajeExito.set(false);
    this.errorMsg.set(null);
    this.progreso.set(0);
    this.progresoTexto.set(this.i18n['btn_analizando']);

    const novedades = this.noticias();
    const payload: ReporteRequest = {
      novedades: novedades.map(n => ({
        fecha_situacion: n.fecha,
        portal_web_url: n.urlPortal,
        texto_situacion: n.textoSituacion,
        imagenes: n.imagenUrl ? [{ url: n.imagenUrl, descripcion: n.imagenDesc }] : [],
      })),
    };

    let progresoActual = 0;
    const intervalo = setInterval(() => {
      progresoActual = Math.min(progresoActual + 5, 90);
      this.progreso.set(progresoActual);
    }, 300);

    this.sub?.unsubscribe();
    this.sub = this.reporteService.analizarIA(payload).subscribe({
      next: (analisis) => {
        clearInterval(intervalo);
        this.cargando.set(false);
        this.analisisGenerado.set(analisis);
        this.fase.set('preview');
        window.scrollTo({ top: 0, behavior: 'smooth' });
      },
      error: (err: Error) => {
        clearInterval(intervalo);
        this.cargando.set(false);
        this.progreso.set(0);
        this.errorMsg.set(err.message);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      },
    });
  }

  volverAEdicion() {
    this.fase.set('input');
  }

  actualizarAnalisis(index: number, campo: keyof AnalisisIA, valor: string) {
    this.analisisGenerado.update(arr => {
      const copy = [...arr];
      if (campo === 'actores') {
        copy[index] = { ...copy[index], actores: valor.split(',').map(a => a.trim()).filter(a => a) };
      } else {
        copy[index] = { ...copy[index], [campo]: valor };
      }
      return copy;
    });
  }

  generarDocumentoFinal() {
    this.cargando.set(true);
    this.mensajeExito.set(false);
    this.errorMsg.set(null);
    this.progreso.set(0);
    this.progresoTexto.set('Generando documento...');

    const novedades = this.noticias();
    const payload: GenerarWordRequest = {
      novedades: novedades.map(n => ({
        fecha_situacion: n.fecha,
        portal_web_url: n.urlPortal,
        texto_situacion: n.textoSituacion,
        imagenes: n.imagenUrl ? [{ url: n.imagenUrl, descripcion: n.imagenDesc }] : [],
      })),
      analisis_por_novedad: this.analisisGenerado(),
    };

    let progresoActual = 0;
    const intervalo = setInterval(() => {
      progresoActual = Math.min(progresoActual + 5, 90);
      this.progreso.set(progresoActual);
    }, 300);

    this.sub?.unsubscribe();
    this.sub = this.reporteService.generarWord(payload).subscribe({
      next: (blob) => {
        clearInterval(intervalo);
        this.progreso.set(100);
        this.progresoTexto.set(this.i18n['progreso_completado']);
        setTimeout(() => this._descargarBlob(blob), 200);
        setTimeout(() => {
          this.cargando.set(false);
          this.progreso.set(0);
          this.mensajeExito.set(true);
          this.fase.set('input');
          window.scrollTo({ top: 0, behavior: 'smooth' });
          setTimeout(() => this.mensajeExito.set(false), 6000);
        }, 500);
      },
      error: (err: Error) => {
        clearInterval(intervalo);
        this.cargando.set(false);
        this.progreso.set(0);
        this.errorMsg.set(err.message);
        window.scrollTo({ top: 0, behavior: 'smooth' });
      },
    });
  }

  ngOnDestroy() {
    this.sub?.unsubscribe();
    this.busquedaSub?.unsubscribe();
  }
}
