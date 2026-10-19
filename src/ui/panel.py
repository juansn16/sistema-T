"""Panel visual ligero (tkinter): estado, log y control del sistema."""

import tkinter as tk
from tkinter import ttk

from .. import config
from ..core import controller as ctrl

COLORES_ESTADO = {
    ctrl.ESTADO_ACTIVO: "#1a7f37",
    ctrl.ESTADO_PAUSADO: "#b7791f",
    ctrl.ESTADO_INICIANDO: "#1f6feb",
    ctrl.ESTADO_ERROR: "#c53030",
    ctrl.ESTADO_DETENIDO: "#57606a",
}

MAX_LINEAS_LOG = 500


class PanelApp:
    def __init__(self, controlador, root=None):
        self.ctrl = controlador
        self.root = root if root is not None else tk.Tk()
        self.root.title("Sistema-T - Dictado de profesiones")
        self.root.geometry("620x420")
        self.root.minsize(520, 340)
        self.root.protocol("WM_DELETE_WINDOW", self._on_cerrar)

        self._fijado = False
        self._construir()
        self.root.after(config.POLL_INTERVAL_MS, self._poll)

    # ------------------------------------------------------------------ #
    # Construcción de la UI
    # ------------------------------------------------------------------ #
    def _construir(self):
        contenedor = ttk.Frame(self.root, padding=10)
        contenedor.pack(fill="both", expand=True)

        # Fila de estado
        fila_estado = ttk.Frame(contenedor)
        fila_estado.pack(fill="x")

        ttk.Label(fila_estado, text="Estado:").pack(side="left")
        self.lbl_estado = tk.Label(
            fila_estado,
            text="DETENIDO",
            foreground="white",
            background=COLORES_ESTADO[ctrl.ESTADO_DETENIDO],
            padx=10,
            pady=2,
        )
        self.lbl_estado.pack(side="left", padx=(6, 0))

        self.btn_toggle = ttk.Button(fila_estado, text="Activar/Pausar", command=self._on_toggle)
        self.btn_toggle.pack(side="right")
        ttk.Button(fila_estado, text="Salir", command=self._on_cerrar).pack(side="right", padx=6)
        self.btn_fijar = ttk.Button(fila_estado, text="Fijar", command=self._on_fijar)
        self.btn_fijar.pack(side="right")

        ttk.Label(
            contenedor,
            text=f"Atajos: {config.HOTKEY_TOGGLE} activar/pausar  |  {config.HOTKEY_QUIT} salir",
            foreground="#57606a",
        ).pack(anchor="w", pady=(6, 2))

        # Umbral de confianza (fuzzy): ajustable en caliente
        fila_umbral = ttk.Frame(contenedor)
        fila_umbral.pack(fill="x", pady=(2, 6))
        ttk.Label(fila_umbral, text="Umbral de confianza:").pack(side="left")
        self.scl_umbral = ttk.Scale(
            fila_umbral,
            from_=config.FUZZY_MIN,
            to=config.FUZZY_MAX,
            orient="horizontal",
            command=self._on_umbral,
        )
        self.scl_umbral.set(self.ctrl.obtener_umbral())
        self.scl_umbral.pack(side="left", fill="x", expand=True, padx=8)
        self.lbl_umbral = ttk.Label(fila_umbral, text=f"{self.ctrl.obtener_umbral()}%", width=4)
        self.lbl_umbral.pack(side="left")

        # Última coincidencia / escritura
        marco_res = ttk.LabelFrame(contenedor, text="Último resultado", padding=8)
        marco_res.pack(fill="x", pady=(4, 6))
        self.lbl_reconocido = ttk.Label(marco_res, text="Reconocido: -")
        self.lbl_reconocido.pack(anchor="w")
        self.lbl_match = ttk.Label(marco_res, text="Coincidencia: -")
        self.lbl_match.pack(anchor="w")
        self.lbl_parcial = ttk.Label(marco_res, text="Escuchando: -", foreground="#57606a")
        self.lbl_parcial.pack(anchor="w")

        # Log
        ttk.Label(contenedor, text="Registro:").pack(anchor="w")
        marco_log = ttk.Frame(contenedor)
        marco_log.pack(fill="both", expand=True)
        self.txt_log = tk.Text(marco_log, height=10, wrap="word", state="disabled")
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(marco_log, command=self.txt_log.yview)
        scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=scroll.set)

    # ------------------------------------------------------------------ #
    # Acciones
    # ------------------------------------------------------------------ #
    def _on_toggle(self):
        self.ctrl.alternar()

    def _on_fijar(self):
        """Ancla / desancla la ventana como siempre-visible (always on top)."""
        self._fijado = not getattr(self, "_fijado", False)
        try:
            self.root.attributes("-topmost", self._fijado)
        except Exception:
            self._fijado = False
        self.btn_fijar.configure(text="Fijado" if self._fijado else "Fijar")

    def _on_umbral(self, valor):
        """Ajusta en caliente el umbral de confianza desde el deslizador."""
        entero = self.ctrl.set_umbral(valor)
        if hasattr(self, "lbl_umbral"):
            self.lbl_umbral.configure(text=f"{entero}%")

    def _on_cerrar(self):
        self.ctrl.solicitar_cierre()

    # ------------------------------------------------------------------ #
    # Refresco periódico de colas (siempre en el hilo de tkinter)
    # ------------------------------------------------------------------ #
    def _poll(self):
        self._drenar_logs()
        self._drenar_estados()
        self._drenar_eventos()

        parcial = self.ctrl.obtener_parcial()
        self.lbl_parcial.configure(text=f"Escuchando: {parcial}" if parcial else "Escuchando: -")

        if self.ctrl.cerrar_solicitado.is_set():
            self._shutdown()
            return

        self.root.after(config.POLL_INTERVAL_MS, self._poll)

    def _drenar_logs(self):
        lineas = []
        while True:
            try:
                lineas.append(self.ctrl.log_queue.get_nowait())
            except Exception:
                break
        if not lineas:
            return
        self.txt_log.configure(state="normal")
        for linea in lineas:
            self.txt_log.insert("end", linea + "\n")
        # Limitar el historial para no crecer sin control
        total = int(self.txt_log.index("end-1c").split(".")[0])
        if total > MAX_LINEAS_LOG:
            self.txt_log.delete("1.0", f"{total - MAX_LINEAS_LOG}.0")
        self.txt_log.see("end")
        self.txt_log.configure(state="disabled")

    def _drenar_estados(self):
        ultimo = None
        while True:
            try:
                ultimo = self.ctrl.estado_queue.get_nowait()
            except Exception:
                break
        if ultimo is None:
            return
        self.lbl_estado.configure(
            text=ultimo,
            background=COLORES_ESTADO.get(ultimo, "#57606a"),
        )

    def _drenar_eventos(self):
        ultimo = None
        while True:
            try:
                ultimo = self.ctrl.evento_queue.get_nowait()
            except Exception:
                break
        if ultimo is None:
            return
        tipo, texto, resultado = ultimo
        self.lbl_reconocido.configure(text=f"Reconocido: {texto}")
        if resultado is None:
            self.lbl_match.configure(text="Coincidencia: sin resultados")
            return
        if tipo == ctrl.EVT_ESCRITO:
            sufijo = "escrito"
        elif tipo == ctrl.EVT_DEBIL:
            sufijo = "débil, NO escrito"
        elif tipo == ctrl.EVT_PAUSADO:
            sufijo = "pausado, NO escrito"
        else:
            sufijo = "error al escribir"
        etiqueta = ctrl.ETIQUETAS_CATEGORIA.get(resultado.categoria, "").strip()
        extra = f" [{etiqueta}]" if etiqueta else ""
        self.lbl_match.configure(
            text=f"Coincidencia: {resultado.nombre} -> {resultado.codigo} "
            f"({resultado.score}%) [{sufijo}]{extra}"
        )

    def _shutdown(self):
        self.ctrl.detener()
        try:
            self.root.destroy()
        except Exception:
            pass

    def run(self):
        self.ctrl.iniciar()
        self.root.mainloop()
