"""Orquestador: une audio, reconocimiento, búsqueda difusa y automatización.

Modelo de concurrencia
-----------------------
* Hilo principal: la GUI de tkinter.
* Hilo "reconocimiento": carga el modelo, abre el micrófono y procesa audio.
* Hilo del listener de pynput: ejecuta los atajos globales.

La comunicación hacia la GUI se hace exclusivamente por colas thread-safe;
la GUI nunca es tocada desde otro hilo.
"""

import queue
import threading

from .. import config
from .audio import CapturaAudio, MicrofonoError
from .ghost_writer import EscritorFantasma
from .hotkeys import GestorAtajos
from .matcher import FuzzyMatcher
from .recognizer import MotorError, VoskEngine

# Estados posibles
ESTADO_INICIANDO = "INICIANDO"
ESTADO_ACTIVO = "ACTIVO"
ESTADO_PAUSADO = "PAUSADO"
ESTADO_ERROR = "ERROR"
ESTADO_DETENIDO = "DETENIDO"

# Tipos de evento hacia la GUI
EVT_ESCRITO = "escrito"
EVT_DEBIL = "debil"
EVT_SIN_MATCH = "sin_match"
EVT_PAUSADO = "pausado"
EVT_ERROR_ESCRITURA = "error_escritura"

# Sufijo de log según el conjunto del que provenga la coincidencia.
ETIQUETAS_CATEGORIA = {
    "profesion": "profesión",
    "ubicacion": "ubicación",
}


class Controlador:
    def __init__(self, catalogo, cfg=config):
        self.cfg = cfg
        self.catalogo = catalogo
        self.umbral = cfg.FUZZY_THRESHOLD
        self.matcher = FuzzyMatcher(catalogo, self.umbral, cfg.FUZZY_SCORER)

        # Colas hacia la GUI
        self.log_queue = queue.Queue()
        self.estado_queue = queue.Queue()
        self.evento_queue = queue.Queue()

        # Flags de control de hilos
        self._stop = threading.Event()
        self._escribir = threading.Event()      # escritura automática habilitada
        self._escribir.set()                    # por defecto activo al arrancar
        self.cerrar_solicitado = threading.Event()
        self._lock = threading.Lock()

        self._hilo_recon = None
        self._captura = None
        self._engine = None
        self.escritor = EscritorFantasma(
            doble_enter=cfg.DOUBLE_ENTER,
            intervalo=cfg.TYPING_INTERVAL,
            failsafe=cfg.PYAUTOGUI_FAILSAFE,
        )
        self._atajos = None

        self._estado = ESTADO_DETENIDO
        self._ultimo_parcial = ""

    # ------------------------------------------------------------------ #
    # API pública
    # ------------------------------------------------------------------ #
    def iniciar(self):
        self._set_estado(ESTADO_INICIANDO)
        self._iniciar_atajos()
        self._hilo_recon = threading.Thread(
            target=self._bucle_reconocimiento, name="reconocimiento", daemon=True
        )
        self._hilo_recon.start()

    def alternar(self):
        """Activa / pausa el envío automático (atajo F8 o botón)."""
        with self._lock:
            # No tiene sentido alternar si el motor no está operativo.
            if self._estado in (ESTADO_ERROR, ESTADO_DETENIDO):
                self.log("No se puede activar/pausar: el motor no está en marcha.")
                return
            if self._escribir.is_set():
                self._escribir.clear()
                self._set_estado(ESTADO_PAUSADO)
                self.log("Pausado: seguirá reconociendo pero no escribirá.")
            else:
                self._escribir.set()
                self._set_estado(ESTADO_ACTIVO)
                self.log("Activo: escribiendo códigos en el formulario.")

    def solicitar_cierre(self):
        self.cerrar_solicitado.set()

    def set_umbral(self, valor):
        """Ajusta en caliente el umbral de coincidencia difusa (0-100)."""
        try:
            valor = int(round(float(valor)))
        except (TypeError, ValueError):
            return self.umbral
        valor = max(self.cfg.FUZZY_MIN, min(self.cfg.FUZZY_MAX, valor))
        if valor != self.umbral:
            self.umbral = valor
            self.matcher.umbral = valor  # visible de inmediato para el hilo de voz
            self.log(f"Umbral de confianza ajustado a {valor}%.")
        return valor

    def obtener_umbral(self):
        return self.umbral

    def detener(self):
        """Parada limpia: señala, detiene atajos y une el hilo de reconocimiento."""
        self._stop.set()
        if self._atajos is not None:
            self._atajos.detener()
        if self._hilo_recon is not None and self._hilo_recon.is_alive():
            self._hilo_recon.join(timeout=3.0)

    def log(self, mensaje):
        self.log_queue.put(mensaje)

    def obtener_parcial(self):
        return self._ultimo_parcial

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    def _set_estado(self, estado):
        self._estado = estado
        self.estado_queue.put(estado)

    def _iniciar_atajos(self):
        self._atajos = GestorAtajos(
            self.cfg.HOTKEY_TOGGLE,
            self.cfg.HOTKEY_QUIT,
            self.alternar,
            self.solicitar_cierre,
        )
        if not self._atajos.disponible():
            self.log("[AVISO] pynput no disponible: atajos globales deshabilitados.")
            return
        try:
            self._atajos.iniciar()
            self.log(
                f"Atajos: {self.cfg.HOTKEY_TOGGLE} activar/pausar, "
                f"{self.cfg.HOTKEY_QUIT} salir."
            )
        except Exception as e:
            self.log(f"[AVISO] No se pudieron registrar los atajos: {e}")

    def _bucle_reconocimiento(self):
        try:
            # 1) Cargar modelo
            self.log("Cargando modelo Vosk (offline)...")
            self._engine = VoskEngine(
                self.cfg.MODEL_DIR,
                self.cfg.SAMPLE_RATE,
                self.catalogo.gramatica,
                self.cfg.USE_GRAMMAR,
                self.cfg.GRAMMAR_ALLOW_UNK,
                self.cfg.VOSK_LOG_LEVEL,
            )
            self.log("Modelo cargado correctamente.")
            if self._engine.nota_gramatica:
                self.log(f"[AVISO] {self._engine.nota_gramatica}")

            # 2) Abrir micrófono
            self.log("Abriendo micrófono...")
            self._captura = CapturaAudio(
                self.cfg.SAMPLE_RATE,
                self.cfg.CHANNELS,
                self.cfg.FRAMES_PER_BUFFER,
                self.cfg.CHUNK_SIZE,
                self.cfg.ENABLE_NOISE_REDUCTION,
            )
            self._captura.abrir()
            self.log("Micrófono listo. Dicta una profesión.")

            # 3) Estado inicial según la preferencia activa/pausa del usuario
            self._set_estado(ESTADO_ACTIVO if self._escribir.is_set() else ESTADO_PAUSADO)

            # 4) Bucle principal de reconocimiento
            while not self._stop.is_set():
                try:
                    datos = self._captura.leer()
                except MicrofonoError as e:
                    self.log(f"[ERROR] {e}")
                    self._set_estado(ESTADO_ERROR)
                    return
                if not datos:
                    continue

                try:
                    texto = self._engine.aceptar(datos)
                    self._ultimo_parcial = self._engine.parcial()
                except MotorError as e:
                    self.log(f"[ERROR] {e}")
                    continue

                if texto:
                    self._ultimo_parcial = ""
                    self._procesar(texto)
        except MotorError as e:
            self.log(f"[ERROR] {e}")
            self._set_estado(ESTADO_ERROR)
        except Exception as e:  # red de seguridad: ningún hilo debe morir en silencio
            self.log(f"[ERROR] Fallo inesperado en el hilo de voz: {e}")
            self._set_estado(ESTADO_ERROR)
        finally:
            if self._captura is not None:
                self._captura.cerrar()
            self.log("Hilo de reconocimiento detenido.")
            # No pisar un estado de ERROR con DETENIDO.
            if self._estado != ESTADO_ERROR:
                self._set_estado(ESTADO_DETENIDO)

    def _procesar(self, texto):
        self.log(f"Reconocido: {texto}")

        resultado = self.matcher.buscar(texto)
        if resultado is None:
            pista = self.matcher.sugerencia(texto)
            if pista:
                self.log(f"[AVISO] {pista}")
            self.evento_queue.put((EVT_SIN_MATCH, texto, None))
            return

        if resultado.bajo_umbral:
            self.log(
                f"Coincidencia débil ({resultado.score}%): "
                f"'{resultado.nombre}' -> {resultado.codigo}. No se escribe."
            )
            self.evento_queue.put((EVT_DEBIL, texto, resultado))
            return

        if not self._escribir.is_set():
            self.log(f"[PAUSADO] '{resultado.nombre}' -> {resultado.codigo} (no escrito)")
            self.evento_queue.put((EVT_PAUSADO, texto, resultado))
            return

        secuencia = self._secuencia_a_escribir(resultado)
        try:
            self.escritor.escribir_secuencia(secuencia)
        except Exception as e:
            self.log(f"[ERROR] No se pudo escribir en el formulario: {e}")
            self.evento_queue.put((EVT_ERROR_ESCRITURA, texto, resultado))
            return

        etiqueta = ETIQUETAS_CATEGORIA.get(resultado.categoria)
        sufijo = f"  [{etiqueta}]" if etiqueta else ""
        self.log(
            f"Escrito: {'-'.join(secuencia)}  "
            f"({resultado.nombre}, {resultado.score}%){sufijo}"
        )
        self.evento_queue.put((EVT_ESCRITO, texto, resultado))

    def _secuencia_a_escribir(self, resultado):
        """Devuelve los códigos a enviar al formulario para `resultado`.

        Para ubicaciones se omite el código de entidad si ESCRIBIR_ENTIDAD está
        desactivado.
        """
        secuencia = list(resultado.secuencia or [resultado.codigo])
        if not getattr(self.cfg, "ESCRIBIR_ENTIDAD", True):
            if getattr(resultado, "categoria", None) == "ubicacion" and len(secuencia) > 1:
                secuencia = secuencia[1:]
        return secuencia
