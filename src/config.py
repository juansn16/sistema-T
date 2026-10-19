"""Configuración central del sistema.

Todos los parámetros ajustables viven aquí para no tocar código de los módulos.
Rutas calculadas de forma absoluta para que funcione sin importar el directorio
desde el que se lance el proceso.
"""

import os

# --------------------------------------------------------------------------- #
# Rutas
# --------------------------------------------------------------------------- #
SRC_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(SRC_DIR)

MODEL_DIR = os.path.join(BASE_DIR, "vosk-model")

# Catálogos que se cargan y fusionan en memoria. Cada entrada: "ruta" + "tipo"
# ("plano" o "territorial"); si se omite "tipo" se autodetecta por la estructura.
DATA_FILES = [
    {
        "tipo": "plano",
        "etiqueta": "profesiones",
        "ruta": os.path.join(SRC_DIR, "models", "codigos-profesiones.json"),
    },
    {
        "tipo": "territorial",
        "etiqueta": "territorial",
        "ruta": os.path.join(SRC_DIR, "models", "divicion-politico-territorial.json"),
    },
]

# Al escribir una ubicación, enviar también el código de la entidad (estado)
# antes del municipio y la parroquia (p. ej. 23 -> 13 -> 16).
ESCRIBIR_ENTIDAD = True

# --------------------------------------------------------------------------- #
# Audio (Vosk trabaja de forma óptima a 16 kHz mono, PCM 16 bits)
# --------------------------------------------------------------------------- #
SAMPLE_RATE = 16000
CHANNELS = 1
CHUNK_SIZE = 4000            # bytes leídos por iteración del bucle
FRAMES_PER_BUFFER = 8192

# Reducción de ruido: activa pero añade latencia. Configurable desde aquí.
ENABLE_NOISE_REDUCTION = False

# --------------------------------------------------------------------------- #
# Reconocimiento
# --------------------------------------------------------------------------- #
# Gramática restringida: limita el reconocedor al vocabulario de profesiones.
USE_GRAMMAR = True
# Permite el token "desconocido" para que el ruido no se fuerce a una profesión.
GRAMMAR_ALLOW_UNK = True
# Nivel de log de Vosk (-1 silencia el ruido de arranque; 0+ muestra detalles).
VOSK_LOG_LEVEL = -1

# --------------------------------------------------------------------------- #
# Búsqueda difusa (fuzzywuzzy)
# --------------------------------------------------------------------------- #
# Score mínimo (0-100) para considerar válida una coincidencia y escribirla.
FUZZY_THRESHOLD = 70
# Límites del control de umbral en la GUI.
FUZZY_MIN = 0
FUZZY_MAX = 100
# Scorer de fuzzywuzzy: WRatio, token_sort_ratio, token_set_ratio, ratio, ...
FUZZY_SCORER = "WRatio"

# --------------------------------------------------------------------------- #
# Automatización (mecanógrafo fantasma)
# --------------------------------------------------------------------------- #
DOUBLE_ENTER = True          # enviar Enter dos veces tras escribir el código
TYPING_INTERVAL = 0.01       # pausa entre pulsaciones (segundos)
PYAUTOGUI_FAILSAFE = True    # mover el ratón a la esquina superior izquierda aborta

# --------------------------------------------------------------------------- #
# Atajos globales (pynput). Formato: "<f8>", "<ctrl>+<alt>+h", ...
# --------------------------------------------------------------------------- #
HOTKEY_TOGGLE = "<f8>"       # activar / pausar el envío automático
HOTKEY_QUIT = "<f9>"         # cerrar la aplicación

# --------------------------------------------------------------------------- #
# Interfaz
# --------------------------------------------------------------------------- #
POLL_INTERVAL_MS = 100       # cada cuánto refresca la GUI las colas de eventos
