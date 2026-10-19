"""Motor de reconocimiento de voz Vosk con gramática restringida opcional."""

import json
import os

from vosk import KaldiRecognizer, Model, SetLogLevel


class MotorError(Exception):
    """Error controlado al cargar el modelo o reconocer."""


def _soporta_gramatica(ruta_modelo):
    """Heurística: los modelos con grafo dinámico incluyen graph/Gr.fst.

    Los modelos "grandes" (p. ej. vosk-model-es-0.42) traen un HCLG.fst estático
    y NO admiten gramáticas en tiempo de ejecución; pasarle una se ignora.
    """
    return os.path.isfile(os.path.join(ruta_modelo, "graph", "Gr.fst"))


class VoskEngine:
    """Envoltura del modelo Vosk.

    Cuando `usar_gramatica` está activo y el modelo lo soporta, se compila una
    gramática a partir de la lista de frases (nombres de profesión) para reducir
    falsos positivos. Si el modelo no admite gramáticas, `nota_gramatica` explica
    por qué se usa reconocimiento libre.
    """

    def __init__(
        self,
        ruta_modelo,
        sample_rate,
        frases=None,
        usar_gramatica=True,
        permitir_unk=True,
        log_level=-1,
    ):
        if not os.path.isdir(ruta_modelo):
            raise MotorError(f"No se encontró la carpeta del modelo Vosk: {ruta_modelo}")

        try:
            SetLogLevel(log_level)
        except Exception:
            pass

        try:
            self.model = Model(ruta_modelo)
        except Exception as e:  # modelo corrupto / incompleto
            raise MotorError(f"No se pudo cargar el modelo Vosk: {e}") from e

        self.sample_rate = sample_rate
        soporta = _soporta_gramatica(ruta_modelo)
        self.gramatica_activa = bool(usar_gramatica and frases and soporta)

        self.nota_gramatica = None
        if usar_gramatica and frases and not soporta:
            self.nota_gramatica = (
                "Este modelo no admite gramática restringida (usa grafo estático); "
                "se usará reconocimiento libre + búsqueda difusa."
            )

        try:
            if self.gramatica_activa:
                vocabulario = [str(f).lower() for f in frases if str(f).strip()]
                if permitir_unk:
                    vocabulario.append("[unk]")
                gramatica = json.dumps(vocabulario, ensure_ascii=False)
                self._reconocedor = KaldiRecognizer(self.model, sample_rate, gramatica)
            else:
                self._reconocedor = KaldiRecognizer(self.model, sample_rate)
        except Exception as e:
            raise MotorError(f"No se pudo inicializar el reconocedor: {e}") from e

    def aceptar(self, datos):
        """Alimenta audio. Devuelve el texto final si la frase terminó, si no None."""
        try:
            if self._reconocedor.AcceptWaveform(datos):
                resultado = json.loads(self._reconocedor.Result())
                return resultado.get("text", "").strip()
        except Exception as e:
            raise MotorError(f"Error durante el reconocimiento: {e}") from e
        return None

    def parcial(self):
        try:
            return json.loads(self._reconocedor.PartialResult()).get("partial", "")
        except Exception:
            return ""

    def finalizar(self):
        """Cierra el audio pendiente y devuelve el texto final.

        Necesario en modo por lotes (Termux): tras alimentar todo el bloque de
        audio hay que forzar el resultado final de Vosk.
        """
        try:
            return json.loads(self._reconocedor.FinalResult()).get("text", "").strip()
        except Exception as e:
            raise MotorError(f"Error al finalizar el reconocimiento: {e}") from e

    def reiniciar(self):
        try:
            self._reconocedor.Reset()
        except Exception:
            pass
