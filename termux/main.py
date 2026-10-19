"""Sistema-T (versión terminal / Termux): reconocimiento por lotes sin GUI.

Dicta una profesión por micrófono; el sistema reconoce el texto de forma local
(Vosk) y muestra en pantalla el código resuelto por búsqueda difusa contra el
catálogo. No escribe en otras aplicaciones (eso no es posible en Termux puro).

Uso:
    python termux/main.py                 # bucle continuo por micrófono
    python termux/main.py --file a.wav    # procesa un archivo (pruebas)
    python termux/main.py --segundos 4    # duración de cada bloque
"""

import argparse
import os
import sys

# Permitir importar tanto "termux.*" como "src.*" desde cualquier directorio.
TERMUX_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(TERMUX_DIR)
for ruta in (BASE_DIR, TERMUX_DIR):
    if ruta not in sys.path:
        sys.path.insert(0, ruta)

from termux import config
from termux.audio_termux import AudioTermuxError, decodificar_a_pcm, grabar_pcm
from src.core.matcher import FuzzyMatcher
from src.core.recognizer import MotorError, VoskEngine
from src.data.loader import CatalogoError, cargar_catalogos

CHUNK = 4000


def reconocer_bloque(engine, pcm):
    """Alimenta Vosk con un bloque PCM y devuelve el texto final."""
    for i in range(0, len(pcm), CHUNK):
        engine.aceptar(pcm[i:i + CHUNK])
    return engine.finalizar()


ETIQUETAS_CATEGORIA = {"profesion": "profesión", "ubicacion": "ubicación"}


def mostrar_resultado(matcher, texto):
    print(f"Reconocido: {texto}")
    resultado = matcher.buscar(texto)
    if resultado is None:
        print("  -> sin coincidencia")
        pista = matcher.sugerencia(texto)
        if pista:
            print(f"     {pista}")
        return
    secuencia = list(resultado.secuencia or [resultado.codigo])
    etiqueta = ETIQUETAS_CATEGORIA.get(resultado.categoria, "")
    etiqueta = f" [{etiqueta}]" if etiqueta else ""
    if resultado.bajo_umbral:
        print(
            f"  -> coincidencia débil: {resultado.nombre} "
            f"[{', '.join(secuencia)}] ({resultado.score}%) - descartada{etiqueta}"
        )
        return
    print(
        f"  -> {resultado.nombre} [{', '.join(secuencia)}] "
        f"({resultado.score}%){etiqueta}"
    )
    if len(secuencia) > 1:
        print("     Escribir (cada código con 2 Enters): " + " -> ".join(secuencia))


def construir_motor(catalogo):
    return VoskEngine(
        config.MODEL_DIR,
        config.SAMPLE_RATE,
        catalogo.gramatica,
        config.USE_GRAMMAR,
        config.GRAMMAR_ALLOW_UNK,
        config.VOSK_LOG_LEVEL,
    )


def parsear_argumentos():
    parser = argparse.ArgumentParser(description="Sistema-T versión terminal (Termux).")
    parser.add_argument("--file", dest="archivo", help="Procesa un archivo de audio en vez del micrófono.")
    parser.add_argument("--segundos", type=int, default=config.RECORD_SECONDS,
                        help=f"Duración de cada bloque de dictado (por defecto {config.RECORD_SECONDS}).")
    return parser.parse_args()


def main():
    args = parsear_argumentos()

    print("=== Sistema-T (terminal) ===")
    print(f"Umbral de confianza: {config.UMBRAL}%")

    try:
        catalogo = cargar_catalogos(config.DATA_FILES)
    except CatalogoError as e:
        print(f"[ERROR] {e}")
        return 1
    print(f"Catálogos cargados: {len(catalogo)} registros.")

    matcher = FuzzyMatcher(catalogo, config.UMBRAL, "WRatio")

    print("Cargando modelo Vosk (offline)...")
    try:
        engine = construir_motor(catalogo)
    except MotorError as e:
        print(f"[ERROR] {e}")
        return 1
    print("Modelo cargado.")
    if engine.nota_gramatica:
        print(f"[AVISO] {engine.nota_gramatica}")

    # Modo archivo (pruebas / dictado offline)
    if args.archivo:
        try:
            pcm = decodificar_a_pcm(args.archivo)
        except AudioTermuxError as e:
            print(f"[ERROR] {e}")
            return 1
        texto = reconocer_bloque(engine, pcm)
        if texto:
            mostrar_resultado(matcher, texto)
        else:
            print("(no se reconoció nada en el archivo)")
        return 0

    # Modo micrófono continuo
    print(
        "\nRecordatorio: se usa el micrófono por defecto de Android. Para dictar con\n"
        "auriculares Bluetooth, asegúrate de que Android enrute la entrada al BT\n"
        "(perfil HFP/manos libres); de lo contrario usará el micrófono interno.\n"
    )
    print(f"Escuchando bloques de {args.segundos}s. Ctrl+C para salir.\n")

    try:
        while True:
            print(f"[grabando {args.segundos}s...]")
            try:
                pcm = grabar_pcm(args.segundos)
            except AudioTermuxError as e:
                print(f"[ERROR] {e}")
                return 1
            texto = reconocer_bloque(engine, pcm)
            if texto:
                mostrar_resultado(matcher, texto)
            else:
                print("(no se reconoció nada)")
            print("-" * 40)
    except KeyboardInterrupt:
        print("\nSaliendo...")
        return 0


if __name__ == "__main__":
    sys.exit(main())
