"""Audio por lotes para Termux: graba con termux-microphone-record y decodifica
a PCM 16 kHz mono con ffmpeg.

El micrófono usado es el que Android tenga por defecto. Para dictar con unos
auriculares Bluetooth hay que lograr que Android enrute la entrada al BT (perfil
HFP/SCO); eso se controla en el sistema, no desde este código.
"""

import os
import shutil
import subprocess
import time

from termux import config


class AudioTermuxError(Exception):
    """Error controlado de grabación/decodificación en Termux."""


def _falta(nombre):
    return shutil.which(nombre) is None


def _verificar_herramientas():
    if _falta(config.MIC_RECORDER):
        raise AudioTermuxError(
            f"No se encontró '{config.MIC_RECORDER}'. Instala: pkg install termux-api "
            "(y la app Termux:API desde F-Droid)."
        )
    if _falta(config.FFMPEG):
        raise AudioTermuxError(f"No se encontró '{config.FFMPEG}'. Instala: pkg install ffmpeg.")


def grabar_pcm(segundos=None):
    """Graba un bloque de audio y lo devuelve como PCM 16-bit mono 16 kHz."""
    _verificar_herramientas()
    segundos = int(segundos or config.RECORD_SECONDS)
    ruta = config.TMP_AUDIO

    if os.path.exists(ruta):
        try:
            os.remove(ruta)
        except OSError:
            pass

    # -l N: termux-microphone-record arranca en segundo plano y se limita a N s.
    inicio = [
        config.MIC_RECORDER,
        "-f", ruta,
        "-l", str(segundos),
        "-r", str(config.SAMPLE_RATE),
        "-c", str(config.CHANNELS),
    ]
    try:
        subprocess.run(inicio, capture_output=True, timeout=15)
    except subprocess.TimeoutExpired:
        _detener()
        raise AudioTermuxError("No se pudo iniciar la grabación (timeout).")
    except OSError as e:
        raise AudioTermuxError(f"No se pudo ejecutar la grabadora: {e}") from e

    # Esperar la ventana de grabación y asegurar la parada.
    time.sleep(segundos + 0.5)
    _detener()
    time.sleep(0.3)

    if not os.path.exists(ruta) or os.path.getsize(ruta) == 0:
        raise AudioTermuxError(
            "No se generó audio. Revisa el permiso de micrófono y que Termux:API esté instalada."
        )
    return decodificar_a_pcm(ruta)


def _detener():
    try:
        subprocess.run([config.MIC_RECORDER, "-d"], capture_output=True, timeout=10)
    except Exception:
        pass


def decodificar_a_pcm(ruta):
    """Decodifica un archivo de audio a PCM 16-bit mono 16 kHz con ffmpeg."""
    if _falta(config.FFMPEG):
        raise AudioTermuxError(f"No se encontró '{config.FFMPEG}'. Instala: pkg install ffmpeg.")
    if not os.path.exists(ruta):
        raise AudioTermuxError(f"No existe el archivo de audio: {ruta}")

    cmd = [
        config.FFMPEG, "-nostdin", "-loglevel", "error",
        "-i", ruta,
        "-ar", str(config.SAMPLE_RATE),
        "-ac", str(config.CHANNELS),
        "-f", "s16le",
        "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0 or not proc.stdout:
        detalle = proc.stderr.decode("utf-8", "replace").strip()
        raise AudioTermuxError(f"ffmpeg no pudo decodificar el audio: {detalle}")
    return proc.stdout
