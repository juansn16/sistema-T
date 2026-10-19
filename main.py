"""Sistema-T: dictado offline de profesiones y ubicaciones para .asp heredados.

Punto de entrada. Carga y fusiona los catálogos (profesiones + división
político-territorial), arranca el controlador (audio + Vosk + búsqueda difusa +
mecanógrafo fantasma) y el panel de control tkinter.

Uso:
    venv\\Scripts\\python.exe main.py
"""

import os
import sys
import tkinter as tk
from tkinter import messagebox

# Asegura que el paquete "src" sea importable al lanzar desde cualquier cwd.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src import config
from src.core.controller import Controlador
from src.data.loader import CatalogoError, cargar_catalogos
from src.ui.panel import PanelApp


def main():
    root = tk.Tk()
    root.withdraw()

    try:
        catalogo = cargar_catalogos(config.DATA_FILES)
    except CatalogoError as e:
        messagebox.showerror("Sistema-T - Error de datos", str(e))
        root.destroy()
        return 1

    controlador = Controlador(catalogo)
    panel = PanelApp(controlador, root=root)
    root.deiconify()
    panel.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
