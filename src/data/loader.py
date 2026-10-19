"""Carga de catálogos <- código.

Los archivos en disco NO se modifican nunca. Se cargan íntegramente en RAM al
iniciar y se normalizan para acelerar la búsqueda difusa.

Formatos aceptados
------------------
* Plano (profesiones):
    - dict  {"ABOGADOS": "008", ...}          (formato canónico actual)
    - list  [{"008": "ABOGADOS"}, ...]        (formato legado)
  Si la orientación clave/valor está invertida, se detecta y se corrige.

* Jerárquico (división político-territorial):
    {
      "entidad": "Zulia", "codigo": "23",
      "municipios": {
        "13": {"nombre": "Maracaibo",
               "parroquias": {"16": "Santa Lucía", ...}}
      }
    }
  Se registra cada parroquia como "MUNICIPIO PARROQUIA" con la secuencia de
  códigos [entidad, municipio, parroquia]. Si el nombre de la parroquia es único
  en todo el estado, se añade además un alias con solo el nombre de la parroquia.
"""

import json
import os
import unicodedata


class CatalogoError(Exception):
    """Error controlado al cargar/validar un catálogo."""


def normalizar(texto):
    """Mayúsculas, sin acentos y con espacios colapsados para comparar."""
    if texto is None:
        return ""
    texto = str(texto).strip().upper()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(texto.split())


def normalizar_gramatica(texto):
    """Normalización para la gramática de Vosk.

    El léxico del modelo es minúsculo, sin acentos y sin puntuación. Limpiar las
    frases antes de compilar la gramática reduce las palabras que quedan fuera
    del vocabulario (y por tanto frases truncadas).
    """
    if texto is None:
        return ""
    t = unicodedata.normalize("NFKD", str(texto))
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    for ch in ',.;:()/-*_"':
        t = t.replace(ch, " ")
    return " ".join(t.split())


def _parece_codigo(valor):
    """Heurística: un código es un token puramente numérico (con ceros a la izq.)."""
    return str(valor).strip().isdigit()


class Catalogo:
    """Catálogo resuelto en memoria: nombre -> (secuencia de códigos).

    Cada registro guarda `secuencia` (lista de códigos a escribir en el
    formulario) y `categoria` (p. ej. "profesion" o "ubicacion").
    """

    def __init__(self, etiqueta="catálogo"):
        self.etiqueta = etiqueta
        self.registros = []      # [{"nombre","codigo","nombre_norm","secuencia","categoria"}]
        self.por_nombre = {}     # nombre_norm -> registro (gana el primero)
        self.nombres = []        # nombres originales
        self.gramatica = []      # frases normalizadas para la gramática de Vosk
        # Nombres que NO deben resolverse por sí solos (ambiguos o a medias):
        # obliga a dictar "municipio + parroquia".
        self.nombres_excluidos = set()

    def __len__(self):
        return len(self.registros)

    def agregar(self, nombre, codigo=None, secuencia=None, categoria=None):
        """Añade un registro.

        Si se pasa `secuencia` (lista de códigos), `codigo` es solo para mostrar
        y por defecto se compone uniendo la secuencia con guiones.
        """
        nombre = str(nombre).strip()
        if not nombre:
            return

        if secuencia is None:
            if codigo is None:
                return
            secuencia = [str(codigo).strip()]
        else:
            secuencia = [str(c).strip() for c in secuencia if str(c).strip()]
            if not secuencia:
                return

        if codigo is None:
            codigo = "-".join(secuencia)
        codigo = str(codigo).strip()
        if not codigo:
            return

        nombre_norm = normalizar(nombre)
        if not nombre_norm:
            return

        registro = {
            "nombre": nombre,
            "codigo": codigo,
            "nombre_norm": nombre_norm,
            "secuencia": secuencia,
            "categoria": categoria,
        }
        self.registros.append(registro)
        self.nombres.append(nombre)
        frase = normalizar_gramatica(nombre)
        if frase:
            self.gramatica.append(frase)
        # Si el nombre ya existe, se conserva el primero (sin tocar el archivo).
        self.por_nombre.setdefault(nombre_norm, registro)


def _leer_json(ruta):
    if not os.path.isfile(ruta):
        raise CatalogoError(f"No se encontró el archivo de catálogo: {ruta}")
    try:
        # utf-8-sig tolera un BOM inicial (habitual al guardar con el Bloc de notas).
        with open(ruta, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise CatalogoError(f"El catálogo no es JSON válido ({ruta}): {e}") from e
    except OSError as e:
        raise CatalogoError(f"No se pudo leer el catálogo ({ruta}): {e}") from e


def _registros_desde_dict(data):
    """Convierte un dict en pares (nombre, codigo) detectando la orientación."""
    pares = []
    for clave, valor in data.items():
        if _parece_codigo(clave) and not _parece_codigo(valor):
            pares.append((valor, clave))   # {codigo: nombre}
        else:
            pares.append((clave, valor))   # {nombre: codigo}
    return pares


def _registros_desde_lista(data):
    """Convierte una lista de dicts de una clave en pares (nombre, codigo)."""
    pares = []
    for item in data:
        if not isinstance(item, dict):
            continue
        for clave, valor in item.items():
            if _parece_codigo(clave) and not _parece_codigo(valor):
                pares.append((valor, clave))
            else:
                pares.append((clave, valor))
    return pares


def _es_territorial(data):
    return isinstance(data, dict) and "municipios" in data


def _volcar_plano(data, ruta, catalogo):
    """Vuelca un catálogo plano {nombre: codigo} en `catalogo`."""
    if isinstance(data, dict):
        pares = _registros_desde_dict(data)
    elif isinstance(data, list):
        pares = _registros_desde_lista(data)
    else:
        raise CatalogoError(
            f"Estructura de catálogo no soportada en {ruta}: {type(data).__name__}"
        )
    for nombre, codigo in pares:
        catalogo.agregar(nombre, codigo, categoria="profesion")


def _volcar_territorial(data, ruta, catalogo, incluir_alias_parroquia=True):
    """Vuelca una división político-territorial jerárquica en `catalogo`."""
    entidad = str(data.get("codigo", "")).strip()
    municipios = data.get("municipios")
    if not isinstance(municipios, dict):
        raise CatalogoError(f"División territorial inválida en {ruta}: falta 'municipios'.")

    # Primer pase: contar cuántas parroquias comparten nombre (para alias únicos)
    # y recoger nombres de municipio, que tampoco son resolubles por sí solos.
    conteo_parroquias = {}
    nombres_municipio = set()
    for mun_cod, mun in municipios.items():
        nombres_municipio.add(normalizar(mun.get("nombre", "")))
        for par_nombre in (mun.get("parroquias") or {}).values():
            clave = normalizar(par_nombre)
            conteo_parroquias[clave] = conteo_parroquias.get(clave, 0) + 1

    # Nombres únicos de parroquia -> se podrán dictar solos (alias).
    alias_unicos = {k for k, n in conteo_parroquias.items() if n == 1 and k}

    # Excluidos: parroquias repetidas y nombres de municipio, salvo que además
    # existan como parroquia única (entonces sí son resolubles por sí solos).
    excluidos = {k for k, n in conteo_parroquias.items() if n > 1 and k}
    excluidos |= {n for n in nombres_municipio if n}
    excluidos -= alias_unicos
    catalogo.nombres_excluidos |= excluidos

    # Segundo pase: registrar cada parroquia.
    for mun_cod, mun in municipios.items():
        mun_cod = str(mun_cod).strip()
        mun_nombre = str(mun.get("nombre", "")).strip()
        parroquias = mun.get("parroquias") or {}
        for par_cod, par_nombre in parroquias.items():
            par_cod = str(par_cod).strip()
            par_nombre = str(par_nombre).strip()
            if not par_nombre:
                continue

            secuencia = [c for c in (entidad, mun_cod, par_cod) if c]
            nombre = f"{mun_nombre} {par_nombre}".strip()
            catalogo.agregar(nombre, secuencia=secuencia, categoria="ubicacion")

            # Alias: solo si el nombre de la parroquia no es ambiguo en el estado.
            if incluir_alias_parroquia and normalizar(par_nombre) in alias_unicos:
                catalogo.agregar(par_nombre, secuencia=secuencia, categoria="ubicacion")


def cargar_catalogo(ruta, etiqueta=None):
    """Carga y normaliza un único catálogo (plano o territorial, autodetectado)."""
    data = _leer_json(ruta)
    catalogo = Catalogo(etiqueta or os.path.basename(ruta))
    if _es_territorial(data):
        _volcar_territorial(data, ruta, catalogo)
    else:
        _volcar_plano(data, ruta, catalogo)
    if len(catalogo) == 0:
        raise CatalogoError(f"El catálogo está vacío o no contiene pares válidos: {ruta}")
    return catalogo


def cargar_catalogos(specs):
    """Carga y fusiona varios catálogos en uno solo.

    `specs` es una lista de dicts con "ruta" y, opcionalmente, "tipo"
    ("plano"|"territorial") y "etiqueta". Si no se indica el tipo se autodetecta.
    """
    catalogo = Catalogo("fusionado")
    for spec in specs:
        ruta = spec["ruta"]
        tipo = spec.get("tipo")
        data = _leer_json(ruta)
        if tipo is None:
            tipo = "territorial" if _es_territorial(data) else "plano"
        if tipo == "territorial":
            _volcar_territorial(data, ruta, catalogo)
        else:
            _volcar_plano(data, ruta, catalogo)

    if len(catalogo) == 0:
        raise CatalogoError("No se cargó ningún registro válido de los catálogos indicados.")
    return catalogo
