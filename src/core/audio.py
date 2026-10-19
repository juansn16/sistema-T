"""Captura de audio del micrófono y reducción de ruido opcional."""

import time

import pyaudio

try:
    import numpy as np
    import noisereduce as nr

    _NR_DISPONIBLE = True
except Exception:  # pragma: no cover - dependencia opcional
    _NR_DISPONIBLE = False


class MicrofonoError(Exception):
    """Error controlado de apertura o lectura del micrófono."""


class CapturaAudio:
    """Envoltura de PyAudio para leer bloques PCM 16-bit mono."""

    def __init__(
        self,
        sample_rate,
        channels,
        frames_per_buffer,
        chunk_size,
        reducir_ruido=False,
    ):
        self.sample_rate = sample_rate
        self.channels = channels
        self.frames_per_buffer = frames_per_buffer
        self.chunk_size = chunk_size
        self.reducir_ruido = reducir_ruido and _NR_DISPONIBLE

        self._pa = None
        self._stream = None

    # ------------------------------------------------------------------ #
    # Ciclo de vida
    # ------------------------------------------------------------------ #
    def abrir(self, reintentos=3, espera=1.5):
        """Abre el stream con reintentos y backoff. Lanza MicrofonoError."""
        ultimo_error = None
        for intento in range(1, reintentos + 1):
            try:
                self._pa = pyaudio.PyAudio()
                self._stream = self._pa.open(
                    format=pyaudio.paInt16,
                    channels=self.channels,
                    rate=self.sample_rate,
                    input=True,
                    frames_per_buffer=self.frames_per_buffer,
                )
                self._stream.start_stream()
                return
            except Exception as e:  # dispositivo ocupado, ausente, driver...
                ultimo_error = e
                self._cerrar_recursos()
                if intento < reintentos:
                    time.sleep(espera)
        raise MicrofonoError(
            f"No se pudo abrir el micrófono tras {reintentos} intentos: {ultimo_error}"
        )

    def leer(self):
        """Devuelve un bloque de bytes. Lanza MicrofonoError si falla."""
        if self._stream is None:
            raise MicrofonoError("El stream de audio no está abierto.")
        try:
            datos = self._stream.read(self.chunk_size, exception_on_overflow=False)
        except Exception as e:
            raise MicrofonoError(f"Error leyendo del micrófono: {e}") from e

        if self.reducir_ruido and datos and len(datos) >= 2:
            datos = self._reducir(datos)
        return datos

    def cerrar(self):
        self._cerrar_recursos()

    # ------------------------------------------------------------------ #
    # Internos
    # ------------------------------------------------------------------ #
    def _cerrar_recursos(self):
        if self._stream is not None:
            try:
                self._stream.stop_stream()
            except Exception:
                pass
            try:
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def _reducir(self, datos):
        try:
            audio = np.frombuffer(datos, dtype=np.int16).astype(np.float32)
            limpio = nr.reduce_noise(y=audio, sr=self.sample_rate, stationary=True)
            limpio = np.clip(limpio, -32768, 32767).astype(np.int16)
            return limpio.tobytes()
        except Exception:
            # Si la reducción falla, devolvemos el audio original sin romper el flujo.
            return datos

    def __enter__(self):
        self.abrir()
        return self

    def __exit__(self, *exc):
        self.cerrar()
        return False
