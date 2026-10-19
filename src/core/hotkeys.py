"""Atajos de teclado globales para controlar el sistema sin tocar el ratón."""

try:
    from pynput import keyboard

    _PYNPUT_DISPONIBLE = True
except Exception:  # pragma: no cover - entorno sin permisos de entrada
    keyboard = None
    _PYNPUT_DISPONIBLE = False


class GestorAtajos:
    """Registra atajos globales.

    Los callbacks se ejecutan en el hilo del listener de pynput: solo deben
    alternar flags/Events thread-safe, nunca tocar la GUI directamente.
    """

    def __init__(self, atajo_toggle, atajo_salir, al_alternar, al_salir):
        self.atajo_toggle = atajo_toggle
        self.atajo_salir = atajo_salir
        self.al_alternar = al_alternar
        self.al_salir = al_salir
        self._listener = None

    @staticmethod
    def disponible():
        return _PYNPUT_DISPONIBLE

    def iniciar(self):
        if not _PYNPUT_DISPONIBLE:
            raise RuntimeError("pynput no está disponible; atajos globales deshabilitados.")
        mapa = {
            self.atajo_toggle: self._on_toggle,
            self.atajo_salir: self._on_salir,
        }
        self._listener = keyboard.GlobalHotKeys(mapa)
        self._listener.daemon = True
        self._listener.start()

    def detener(self):
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def _on_toggle(self):
        try:
            self.al_alternar()
        except Exception:
            pass

    def _on_salir(self):
        try:
            self.al_salir()
        except Exception:
            pass
