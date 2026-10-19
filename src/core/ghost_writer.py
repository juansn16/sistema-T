"""Mecanógrafo fantasma: escribe el código(s) sobre el formulario .asp.

Para una profesión se escribe un código; para una ubicación se escribe la
secuencia [entidad, municipio, parroquia], cada uno seguido de dos Enters.
"""

try:
    import pyautogui

    _PYAUTOGUI_DISPONIBLE = True
except Exception:  # pragma: no cover - entorno sin GUI/permisos
    pyautogui = None
    _PYAUTOGUI_DISPONIBLE = False


class EscritorFantasma:
    """Envía el código resuelto al campo activo del formulario heredado."""

    def __init__(self, doble_enter=True, intervalo=0.01, failsafe=True):
        self.doble_enter = doble_enter
        self.intervalo = intervalo
        if _PYAUTOGUI_DISPONIBLE:
            pyautogui.FAILSAFE = failsafe
            pyautogui.PAUSE = 0

    @staticmethod
    def disponible():
        return _PYAUTOGUI_DISPONIBLE

    def escribir_codigo(self, codigo):
        """Escribe un único código y pulsa Enter (atajo de compatibilidad)."""
        self.escribir_secuencia([codigo])

    def escribir_secuencia(self, secuencia):
        """Escribe una secuencia de códigos, cada uno seguido de Enter.

        Para una ubicación se envía [entidad, municipio, parroquia]: cada código
        va a su campo y se confirma con Enter (dos veces si `doble_enter`).
        """
        if not _PYAUTOGUI_DISPONIBLE:
            raise RuntimeError("pyautogui no está disponible; automatización deshabilitada.")
        for codigo in secuencia:
            pyautogui.write(str(codigo), interval=self.intervalo)
            pyautogui.press("enter")
            if self.doble_enter:
                pyautogui.press("enter")

    def escribir_texto(self, texto):
        if not _PYAUTOGUI_DISPONIBLE:
            raise RuntimeError("pyautogui no está disponible; automatización deshabilitada.")
        pyautogui.write(str(texto), interval=self.intervalo)
