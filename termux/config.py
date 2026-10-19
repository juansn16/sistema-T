"""Configuración de la versión de terminal (Termux) del sistema.

Reutiliza los módulos de src/ y NO usa GUI ni automatización de teclado
(no disponibles en Termux puro).
"""

import os
import tempfile

# --------------------------------------------------------------------------- #
# Rutas (relativas a la carpeta termux/, apuntando al proyecto)
# --------------------------------------------------------------------------- #
TERMUX_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TERMUX_DIR)

MODEL_DIR = os.path.join(BASE_DIR, "vosk-model")

# Catálogos fusionados: profesiones (plano) y división político-territorial.
DATA_FILES = [
    {
        "tipo": "plano",
        "etiqueta": "profesiones",
        "ruta": os.path.join(BASE_DIR, "src", "models", "codigos-profesiones.json"),
    },
    {
        "tipo": "territorial",
        "etiqueta": "territorial",
        "ruta": os.path.join(BASE_DIR, "src", "models", "divicion-politico-territorial.json"),
    },
]

# --------------------------------------------------------------------------- #
# Reconocimiento
# --------------------------------------------------------------------------- #
UMBRAL = 90                  # umbral de confianza (fuzzy) fijo para esta versión
SAMPLE_RATE = 16000
CHANNELS = 1
USE_GRAMMAR = True
GRAMMAR_ALLOW_UNK = True
VOSK_LOG_LEVEL = -1

# --------------------------------------------------------------------------- #
# Audio por lotes (termux-microphone-record)
# --------------------------------------------------------------------------- #
RECORD_SECONDS = 5           # duración de cada bloque de dictado
FFMPEG = "ffmpeg"
MIC_RECORDER = "termux-microphone-record"
TMP_AUDIO = os.path.join(tempfile.gettempdir(), "sistema_t_rec.m4a")
