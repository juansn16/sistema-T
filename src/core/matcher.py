"""Búsqueda difusa: texto dictado -> código.

El operador dicta lenguaje natural ("ingeniero civil", "Maracaibo Santa Lucía");
aquí se busca la coincidencia más cercana en los NOMBRES del catálogo fusionado
(profesiones y ubicaciones) y se devuelve su `secuencia` de códigos. Nunca se
compara contra los códigos.
"""

from dataclasses import dataclass

from fuzzywuzzy import fuzz, process

from ..data.loader import normalizar


@dataclass
class Resultado:
    codigo: str
    nombre: str
    score: int
    bajo_umbral: bool
    secuencia: list = None
    categoria: str = None


def _resolver_scorer(nombre):
    return getattr(fuzz, nombre, fuzz.WRatio)


class FuzzyMatcher:
    def __init__(self, catalogo, umbral, scorer="WRatio"):
        self.catalogo = catalogo
        self.umbral = umbral
        self.scorer = _resolver_scorer(scorer)
        # Copia del índice normalizado para búsqueda rápida.
        self._choices = dict(catalogo.por_nombre)
        self._claves = list(self._choices.keys())
        # Nombres que no se resuelven solos (ambiguos / parciales).
        self.excluidos = set(getattr(catalogo, "nombres_excluidos", None) or set())

    def buscar(self, texto):
        """Devuelve Resultado o None si no hay texto útil."""
        consulta = normalizar(texto)
        if not consulta:
            return None

        # Nombres ambiguos (parroquias repetidas) o parciales (municipios) no se
        # resuelven por sí solos: obligan a dictar "municipio + parroquia".
        if consulta in self.excluidos:
            return None

        # Coincidencia exacta primero (rápida y sin sorpresas).
        exacto = self._choices.get(consulta)
        if exacto is not None:
            return Resultado(
                exacto["codigo"],
                exacto["nombre"],
                100,
                False,
                exacto.get("secuencia"),
                exacto.get("categoria"),
            )

        coincidencia = process.extractOne(consulta, self._claves, scorer=self.scorer)
        if not coincidencia:
            return None

        clave, score = coincidencia
        registro = self._choices[clave]
        return Resultado(
            registro["codigo"],
            registro["nombre"],
            score,
            score < self.umbral,
            registro.get("secuencia"),
            registro.get("categoria"),
        )

    def sugerencia(self, texto):
        """Pista para el operador si `texto` coincide con un nombre excluido."""
        consulta = normalizar(texto)
        if consulta and consulta in self.excluidos:
            return f"'{consulta}' es ambiguo: dicta municipio + parroquia."
        return None
