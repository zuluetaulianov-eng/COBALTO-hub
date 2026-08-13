import tkinter as tk
from tkinter import scrolledtext, ttk
import urllib.request
import json
import threading
import time

try:
    from informe_osint import generar_informe_osint
    from fuente_datos import cargar_informe
    from chat_docx import chat_desde_historial, generar_transcripcion
    REPORTE_DISPONIBLE = True
except ImportError:
    generar_informe_osint = None
    cargar_informe = None
    chat_desde_historial = None
    generar_transcripcion = None
    REPORTE_DISPONIBLE = False

# ─── Paleta ───────────────────────────────────────────────────────────────────
BG_DARK    = "#0d1117"
BG_PANEL   = "#161b22"
BG_INPUT   = "#21262d"
ACCENT     = "#58a6ff"
ACCENT2    = "#3fb950"
TEXT_MAIN  = "#e6edf3"
TEXT_DIM   = "#8b949e"
TEXT_ERR   = "#f85149"
BORDER     = "#30363d"


class OllamaChat:
    def __init__(self, root):
        self.root = root
        self.root.title("🤖 Ollama Chat — Pruebas de IA Local")
        self.root.geometry("860x680")
        self.root.minsize(640, 520)
        self.root.configure(bg=BG_DARK)

        self.streaming    = False
        self.chat_history = []
        self.token_count  = 0
        self.start_time   = None

        self._build_ui()
        self._append_system("Listo. Configura la conexión, escribe tu mensaje y presiona Enviar.")
        self.msg_entry.focus()

    # ──────────────────────────────────────────────────────────────────────────
    def _build_ui(self):

        # ── BARRA SUPERIOR ────────────────────────────────────────────────────
        top = tk.Frame(self.root, bg=BG_PANEL)
        top.pack(fill=tk.X)

        tk.Label(top, text="🤖  OLLAMA CHAT", bg=BG_PANEL, fg=ACCENT,
                 font=("Segoe UI", 13, "bold")).pack(side=tk.LEFT, padx=14, pady=8)

        self.status_dot = tk.Label(top, text="●", bg=BG_PANEL, fg=TEXT_DIM,
                                   font=("Segoe UI", 13))
        self.status_dot.pack(side=tk.RIGHT, padx=(0, 12), pady=8)
        self.status_lbl = tk.Label(top, text="Desconectado", bg=BG_PANEL, fg=TEXT_DIM,
                                   font=("Segoe UI", 8))
        self.status_lbl.pack(side=tk.RIGHT, pady=8)

        # ── FILA 1 DE CONFIGURACIÓN ───────────────────────────────────────────
        r1 = tk.Frame(self.root, bg=BG_PANEL, pady=5)
        r1.pack(fill=tk.X, padx=12)

        self._lbl(r1, "Tu nombre:")
        self.name_entry = self._entry(r1, "Ulianov", 10, fg=ACCENT)
        self.name_entry.pack(side=tk.LEFT, padx=(0, 16), ipady=3)

        self._lbl(r1, "IP del servidor:")
        self.ip_entry = self._entry(r1, "192.168.1.213", 15)
        self.ip_entry.pack(side=tk.LEFT, padx=(0, 8), ipady=3)

        self._lbl(r1, "Puerto:")
        self.port_entry = self._entry(r1, "11434", 6)
        self.port_entry.pack(side=tk.LEFT, padx=(0, 16), ipady=3)

        self._lbl(r1, "Modelo:")
        self.model_var = tk.StringVar(value="llama3.2")
        self.model_combo = ttk.Combobox(r1, textvariable=self.model_var,
                                        width=16, font=("Segoe UI", 10))
        self.model_combo['values'] = ["llama3.2", "llama3", "mistral",
                                      "gemma2", "phi3", "qwen2"]
        self.model_combo.pack(side=tk.LEFT, padx=(0, 6), ipady=2)

        self.detect_btn = self._btn(r1, "⟳ Detectar", self._detect_models,
                                    BG_INPUT, ACCENT, 8)
        self.detect_btn.pack(side=tk.LEFT)

        # ── FILA 2 DE CONFIGURACIÓN ───────────────────────────────────────────
        r2 = tk.Frame(self.root, bg=BG_PANEL, pady=5)
        r2.pack(fill=tk.X, padx=12)

        self._lbl(r2, "Temperatura:")
        self.temp_var = tk.DoubleVar(value=0.7)
        tk.Scale(r2, from_=0.0, to=2.0, resolution=0.05,
                 orient=tk.HORIZONTAL, variable=self.temp_var,
                 bg=BG_PANEL, fg=TEXT_MAIN, activebackground=ACCENT,
                 troughcolor=BG_INPUT, highlightthickness=0,
                 length=100, sliderlength=14, width=7,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(0, 2))
        tk.Label(r2, textvariable=self.temp_var,
                 bg=BG_PANEL, fg=ACCENT, font=("Segoe UI", 9, "bold"),
                 width=4).pack(side=tk.LEFT, padx=(0, 16))

        self.stream_var = tk.BooleanVar(value=True)
        tk.Checkbutton(r2, text="Streaming", variable=self.stream_var,
                       bg=BG_PANEL, fg=TEXT_DIM, selectcolor=BG_INPUT,
                       activebackground=BG_PANEL, activeforeground=TEXT_MAIN,
                       font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 16))

        self._lbl(r2, "System prompt:")
        self.sys_entry = self._entry(r2, "Eres un asistente de IA local útil y conciso.", 38)
        self.sys_entry.pack(side=tk.LEFT, padx=(0, 8), ipady=3, fill=tk.X, expand=True)

        # ── SEPARADOR ─────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        # ── ÁREA DE CHAT (expansible) ─────────────────────────────────────────
        self.chat_area = scrolledtext.ScrolledText(
            self.root, wrap=tk.WORD, state='disabled',
            font=("Segoe UI", 11), bg=BG_DARK, fg=TEXT_MAIN,
            relief=tk.FLAT, bd=0,
            selectbackground=ACCENT, selectforeground=BG_DARK,
            padx=16, pady=10
        )
        self.chat_area.pack(fill=tk.BOTH, expand=True)

        # Tags de color
        self.chat_area.tag_config("user_pre",  foreground=ACCENT,    font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("user_txt",  foreground=TEXT_MAIN, font=("Segoe UI", 11))
        self.chat_area.tag_config("bot_pre",   foreground=ACCENT2,   font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("bot_txt",   foreground=TEXT_MAIN, font=("Segoe UI", 11))
        self.chat_area.tag_config("sys",       foreground=TEXT_DIM,  font=("Segoe UI", 9,  "italic"))
        self.chat_area.tag_config("error",     foreground=TEXT_ERR,  font=("Segoe UI", 10, "bold"))
        self.chat_area.tag_config("sep",       foreground="#21262d", font=("Segoe UI", 5))

        # ── BARRA DE STATS ────────────────────────────────────────────────────
        stats = tk.Frame(self.root, bg=BG_PANEL)
        stats.pack(fill=tk.X)

        self.tokens_lbl = tk.Label(stats, text="Tokens: 0", bg=BG_PANEL,
                                   fg=TEXT_DIM, font=("Segoe UI", 8))
        self.tokens_lbl.pack(side=tk.LEFT, padx=14, pady=3)

        self.time_lbl = tk.Label(stats, text="", bg=BG_PANEL,
                                 fg=TEXT_DIM, font=("Segoe UI", 8))
        self.time_lbl.pack(side=tk.LEFT)

        self.typing_lbl = tk.Label(stats, text="", bg=BG_PANEL,
                                   fg=ACCENT2, font=("Segoe UI", 8, "italic"))
        self.typing_lbl.pack(side=tk.LEFT, padx=10)

        # ── SEPARADOR ─────────────────────────────────────────────────────────
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=tk.X)

        # ══════════════════════════════════════════════════════════════════════
        # ── ZONA DE ENTRADA DEL USUARIO ───────────────────────────────────────
        # ══════════════════════════════════════════════════════════════════════
        inp_frame = tk.Frame(self.root, bg=BG_PANEL)
        inp_frame.pack(fill=tk.X, padx=12, pady=10)

        # Etiqueta visible
        tk.Label(inp_frame, text="✏  Escribe tu mensaje:",
                 bg=BG_PANEL, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(anchor=tk.W, pady=(0, 4))

        # Fila con text box + botones
        inp_row = tk.Frame(inp_frame, bg=BG_PANEL)
        inp_row.pack(fill=tk.X)

        # Caja de texto principal (altura fija = 4 líneas)
        self.msg_entry = tk.Text(
            inp_row, height=4,
            font=("Segoe UI", 12),
            bg=BG_INPUT, fg=TEXT_MAIN,
            insertbackground=ACCENT,
            relief=tk.FLAT, bd=0,
            wrap=tk.WORD
        )
        self.msg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True,
                            ipady=6, padx=(0, 10))
        self.msg_entry.bind("<Return>",       self._on_enter)
        self.msg_entry.bind("<Shift-Return>", lambda e: None)
        self.msg_entry.bind("<KeyRelease>",   self._update_char_count)

        # Columna de botones
        btn_col = tk.Frame(inp_row, bg=BG_PANEL)
        btn_col.pack(side=tk.RIGHT, fill=tk.Y)

        self.send_btn = self._btn(btn_col, "▶  Enviar", self._send,
                                  ACCENT, BG_DARK, 11)
        self.send_btn.pack(fill=tk.X, pady=(0, 6))

        self.clear_btn = self._btn(btn_col, "🗑 Limpiar", self._clear_chat,
                                   BG_INPUT, TEXT_DIM, 9)
        self.clear_btn.pack(fill=tk.X)

        self.export_btn = self._btn(btn_col, "⬇ Exportar informe", self._export_informe,
                                    BG_INPUT, ACCENT, 9)
        self.export_btn.pack(fill=tk.X, pady=(8, 0))

        self.export_chat_btn = self._btn(btn_col, "💬 Exportar IA", self._export_chat,
                                         BG_INPUT, ACCENT2, 9)
        self.export_chat_btn.pack(fill=tk.X, pady=(6, 0))
        if not REPORTE_DISPONIBLE:
            self.export_btn.config(state=tk.DISABLED)
            self.export_chat_btn.config(state=tk.DISABLED)

        # Contador de caracteres
        self.char_lbl = tk.Label(inp_frame,
                                 text="Enter = Enviar  |  Shift+Enter = Salto de línea",
                                 bg=BG_PANEL, fg=TEXT_DIM, font=("Segoe UI", 7))
        self.char_lbl.pack(anchor=tk.E, pady=(4, 0))

    # ──────────────────────────────────────────────────────────────────────────
    # WIDGET HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _lbl(self, parent, text):
        tk.Label(parent, text=text, bg=BG_PANEL, fg=TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 4))

    def _entry(self, parent, default, width, fg=None):
        e = tk.Entry(parent, width=width, font=("Segoe UI", 10),
                     bg=BG_INPUT, fg=fg or TEXT_MAIN,
                     insertbackground=ACCENT, relief=tk.FLAT, bd=0)
        e.insert(0, default)
        return e

    def _btn(self, parent, text, cmd, bg, fg, fsize=10):
        b = tk.Button(parent, text=text, command=cmd,
                      bg=bg, fg=fg,
                      activebackground=ACCENT, activeforeground=BG_DARK,
                      font=("Segoe UI", fsize, "bold"),
                      relief=tk.FLAT, bd=0, padx=12, pady=6, cursor="hand2")
        b.bind("<Enter>", lambda e, _b=b:       _b.configure(bg=ACCENT,  fg=BG_DARK))
        b.bind("<Leave>", lambda e, _b=b, ob=bg, of=fg: _b.configure(bg=ob, fg=of))
        return b

    # ──────────────────────────────────────────────────────────────────────────
    # STATUS / APPEND HELPERS
    # ──────────────────────────────────────────────────────────────────────────
    def _set_status(self, text, color):
        self.status_lbl.config(text=text, fg=color)
        self.status_dot.config(fg=color)

    def _append(self, text, tag):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, text, tag)
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)

    def _append_system(self, msg):
        self._append(f"\n  ℹ  {msg}\n", "sys")

    def _append_sep(self):
        self._append("\n" + "─" * 90 + "\n", "sep")

    def _update_char_count(self, event=None):
        n = len(self.msg_entry.get("1.0", tk.END).strip())
        self.char_lbl.config(
            text=f"{n} car.  |  Enter = Enviar  |  Shift+Enter = Salto de línea")

    # ──────────────────────────────────────────────────────────────────────────
    # DETECT MODELS
    # ──────────────────────────────────────────────────────────────────────────
    def _detect_models(self):
        self._set_status("Detectando modelos…", ACCENT)
        self.detect_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._do_detect, daemon=True).start()

    def _do_detect(self):
        ip   = self.ip_entry.get().strip()
        port = self.port_entry.get().strip()
        try:
            req = urllib.request.Request(f"http://{ip}:{port}/api/tags")
            with urllib.request.urlopen(req, timeout=8) as r:
                data = json.loads(r.read())
            models = [m["name"] for m in data.get("models", [])]
            if models:
                self.root.after(0, self._set_models, models)
            else:
                self.root.after(0, self._append_system, "No se encontraron modelos.")
                self.root.after(0, self._set_status, "Sin modelos", TEXT_ERR)
        except Exception as ex:
            self.root.after(0, self._append_system, f"Error al detectar: {ex}")
            self.root.after(0, self._set_status, "Error", TEXT_ERR)
        finally:
            self.root.after(0, self.detect_btn.config, {"state": tk.NORMAL})

    def _set_models(self, models):
        self.model_combo['values'] = models
        self.model_var.set(models[0])
        self._set_status(f"{len(models)} modelo(s)", ACCENT2)
        self._append_system(f"Modelos: {', '.join(models)}")

    # ──────────────────────────────────────────────────────────────────────────
    # SEND
    # ──────────────────────────────────────────────────────────────────────────
    def _on_enter(self, event):
        if not (event.state & 0x1):   # sin Shift
            self._send()
            return "break"

    def _send(self, event=None):
        user_msg = self.msg_entry.get("1.0", tk.END).strip()
        if not user_msg or self.streaming:
            return

        self.msg_entry.delete("1.0", tk.END)
        self._update_char_count()

        user_name = self.name_entry.get().strip() or "Tú"

        self._append_sep()
        self._append(f"  {user_name}  ", "user_pre")
        self._append(f"\n{user_msg}\n", "user_txt")

        sys_prompt = self.sys_entry.get().strip()
        messages = []
        if sys_prompt:
            messages.append({"role": "system", "content": sys_prompt})
        messages += self.chat_history
        messages.append({"role": "user", "content": user_msg})
        self.chat_history.append({"role": "user", "content": user_msg})

        self.streaming   = True
        self.start_time  = time.time()
        self._lock_ui(True)
        self._set_status("Generando…", ACCENT)
        self.typing_lbl.config(text="● pensando…")

        target = self._call_stream if self.stream_var.get() else self._call_sync
        threading.Thread(target=target, args=(messages,), daemon=True).start()

    # ──────────────────────────────────────────────────────────────────────────
    # API – STREAMING
    # ──────────────────────────────────────────────────────────────────────────
    def _call_stream(self, messages):
        ip, port  = self.ip_entry.get().strip(), self.port_entry.get().strip()
        model     = self.model_var.get().strip()
        temp      = round(self.temp_var.get(), 2)
        url       = f"http://{ip}:{port}/api/chat"
        payload   = {"model": model, "messages": messages,
                     "stream": True, "options": {"temperature": temp}}
        data      = json.dumps(payload).encode("utf-8")
        req       = urllib.request.Request(url, data=data,
                                           headers={"Content-Type": "application/json"})
        full      = ""
        first     = True
        self.root.after(0, self._append, "\n  Ollama  ", "bot_pre")
        self.root.after(0, self._append, "\n",           "bot_txt")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                for raw in resp:
                    if not raw.strip():
                        continue
                    chunk = json.loads(raw.decode("utf-8"))
                    token = chunk.get("message", {}).get("content", "")
                    full += token
                    self.token_count += 1
                    if first:
                        self.root.after(0, self.typing_lbl.config, {"text": "● escribiendo…"})
                        first = False
                    self.root.after(0, self._stream_tok, token)
                    if chunk.get("done"):
                        break
            self.chat_history.append({"role": "assistant", "content": full})
            self.root.after(0, self._finish, time.time() - self.start_time)
        except Exception as ex:
            self.root.after(0, self._append, f"\n  ⚠  Error: {ex}\n", "error")
            self.root.after(0, self._set_status, "Error", TEXT_ERR)
            self.root.after(0, self.typing_lbl.config, {"text": ""})
            self.root.after(0, self._lock_ui, False)
            self.streaming = False

    def _stream_tok(self, token):
        self.chat_area.config(state='normal')
        self.chat_area.insert(tk.END, token, "bot_txt")
        self.chat_area.config(state='disabled')
        self.chat_area.yview(tk.END)
        self.tokens_lbl.config(text=f"Tokens: {self.token_count}")

    # ──────────────────────────────────────────────────────────────────────────
    # API – SIN STREAMING
    # ──────────────────────────────────────────────────────────────────────────
    def _call_sync(self, messages):
        ip, port  = self.ip_entry.get().strip(), self.port_entry.get().strip()
        model     = self.model_var.get().strip()
        temp      = round(self.temp_var.get(), 2)
        url       = f"http://{ip}:{port}/api/chat"
        payload   = {"model": model, "messages": messages,
                     "stream": False, "options": {"temperature": temp}}
        data      = json.dumps(payload).encode("utf-8")
        req       = urllib.request.Request(url, data=data,
                                           headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                res  = json.loads(resp.read())
            bot_msg = res.get("message", {}).get("content", "")
            self.chat_history.append({"role": "assistant", "content": bot_msg})
            self.token_count += res.get("eval_count", len(bot_msg.split()))
            self.root.after(0, self._append, "\n  Ollama  ", "bot_pre")
            self.root.after(0, self._append, f"\n{bot_msg}\n", "bot_txt")
            self.root.after(0, self._finish, time.time() - self.start_time)
        except Exception as ex:
            self.root.after(0, self._append, f"\n  ⚠  Error: {ex}\n", "error")
            self.root.after(0, self._set_status, "Error", TEXT_ERR)
            self.root.after(0, self.typing_lbl.config, {"text": ""})
            self.root.after(0, self._lock_ui, False)
            self.streaming = False

    # ──────────────────────────────────────────────────────────────────────────
    # POST-RESPONSE
    # ──────────────────────────────────────────────────────────────────────────
    def _finish(self, elapsed):
        self._append("\n", "bot_txt")
        self.tokens_lbl.config(text=f"Tokens: {self.token_count}")
        self.time_lbl.config(text=f"  ⏱ {elapsed:.1f}s")
        self.typing_lbl.config(text="")
        self._set_status("Listo", ACCENT2)
        self._lock_ui(False)
        self.streaming = False
        self.msg_entry.focus()

    def _lock_ui(self, locked):
        s = tk.DISABLED if locked else tk.NORMAL
        self.send_btn.config(state=s, text="⌛ Generando…" if locked else "▶  Enviar")
        self.msg_entry.config(state=s)

    # ──────────────────────────────────────────────────────────────────────────
    # EXPORTAR INFORME OSINT (DOCX)
    # ──────────────────────────────────────────────────────────────────────────
    def _export_informe(self):
        if not REPORTE_DISPONIBLE:
            self._append_system("Informe no disponible: requiere python-docx y Pillow.")
            return
        self._set_status("Generando informe…", ACCENT)
        self.export_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._do_export, daemon=True).start()

    def _do_export(self):
        try:
            resultado = cargar_informe()
            ruta = generar_informe_osint(resultado.datos)
            self.root.after(0, self._finish_export,
                            ruta, resultado.resumen, list(resultado.errores))
        except Exception as ex:
            self.root.after(0, self._export_error, str(ex))

    def _finish_export(self, ruta, resumen, errores):
        self.export_btn.config(state=tk.NORMAL)
        self._set_status("Informe listo", ACCENT2)
        self._append_system(f"Informe DOCX generado: {ruta}")
        self._append_system(f"Origen de datos: {resumen}")
        for e in errores:
            self._append_system(f"Advertencia: {e}")

    def _export_error(self, msg):
        self.export_btn.config(state=tk.NORMAL)
        self._set_status("Error", TEXT_ERR)
        self._append_system(f"Error al exportar: {msg}")

    # ──────────────────────────────────────────────────────────────────────────
    # EXPORTAR TRANSCRIPCIÓN DE IA (DOCX)
    # ──────────────────────────────────────────────────────────────────────────
    def _export_chat(self):
        if not self.chat_history:
            self._append_system("No hay conversación que exportar.")
            return
        self._set_status("Exportando conversación…", ACCENT2)
        self.export_chat_btn.config(state=tk.DISABLED)
        threading.Thread(target=self._do_export_chat, daemon=True).start()

    def _do_export_chat(self):
        try:
            historial = list(self.chat_history)
            nombre = self.name_entry.get().strip() or "Tú"
            modelo = self.model_var.get().strip() or "llama3.2"
            temp = round(self.temp_var.get(), 2)
            fecha = time.strftime("%d/%m/%Y %H:%M")
            datos = chat_desde_historial(historial, nombre, modelo, temp, fecha)
            ruta = generar_transcripcion(datos)
            self.root.after(0, self._finish_export_chat,
                            ruta, len(historial))
        except Exception as ex:
            self.root.after(0, self._export_chat_error, str(ex))

    def _finish_export_chat(self, ruta, n_msgs):
        self.export_chat_btn.config(state=tk.NORMAL)
        self._set_status("Conversación exportada", ACCENT2)
        self._append_system(f"Transcripción DOCX generada: {ruta} "
                            f"({n_msgs} mensajes)")

    def _export_chat_error(self, msg):
        self.export_chat_btn.config(state=tk.NORMAL)
        self._set_status("Error", TEXT_ERR)
        self._append_system(f"Error al exportar conversación: {msg}")

    # ──────────────────────────────────────────────────────────────────────────
    # LIMPIAR
    # ──────────────────────────────────────────────────────────────────────────
    def _clear_chat(self):
        self.chat_history = []
        self.token_count  = 0
        self.chat_area.config(state='normal')
        self.chat_area.delete("1.0", tk.END)
        self.chat_area.config(state='disabled')
        self.tokens_lbl.config(text="Tokens: 0")
        self.time_lbl.config(text="")
        self._set_status("Desconectado", TEXT_DIM)
        self._append_system("Historial borrado. Nueva sesión iniciada.")
        self.msg_entry.focus()


# ─── Main ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    root = tk.Tk()
    root.tk_setPalette(background=BG_DARK)

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TCombobox",
                    fieldbackground=BG_INPUT, background=BG_INPUT,
                    foreground=TEXT_MAIN, arrowcolor=ACCENT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    style.map("TCombobox",
              fieldbackground=[("readonly", BG_INPUT)],
              foreground=[("readonly", TEXT_MAIN)],
              background=[("readonly", BG_INPUT)])

    app = OllamaChat(root)
    root.mainloop()
