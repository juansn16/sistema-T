# Sistema-T — Versión terminal (Termux)

Versión ligera, **sin interfaz gráfica**, pensada para ejecutarse en Termux (Android).
Dicta por micrófono una **profesión** o una **ubicación** ("municipio + parroquia"):
el sistema reconoce el texto localmente con **Vosk**, busca por nombre con **búsqueda
difusa** sobre los catálogos fusionados y muestra en pantalla el/los **códigos**.

- Umbral de confianza **fijo en 90%** (`termux/config.py`).
- **No** escribe en otras aplicaciones (no es posible en Termux puro sin root/X11):
  muestra los códigos y el orden en que habría que escribirlos.
- Reutiliza los módulos de `src/` (`loader`, `matcher`, `recognizer`).

## Requisitos en Termux

```bash
pkg update && pkg upgrade
pkg install python ffmpeg termux-api
pip install vosk fuzzywuzzy
```

- `termux-api` (paquete) **y** la app **Termux:API** instalada desde F-Droid/Play.
- `python-Levenshtein` es opcional: si no compila, `fuzzywuzzy` usa un respaldo
  (`difflib`) más lento pero funcional.

> **Nota sobre Vosk:** no existe wheel oficial para la Python de Android. Si
> `pip install vosk` falla, usa un entorno Linux real con
> [proot-distro](https://github.com/juansn16/sistema-T.git) (p. ej. Ubuntu), donde
> `vosk` instala sin problema; esta versión funciona igual dentro de proot.

## Copiar el proyecto

Copia la carpeta completa del proyecto a Termux, incluyendo:

```
sistema-T/
├── vosk-model/                 # modelo local de Vosk (obligatorio)
├── src/                        # módulos compartidos
├── src/models/codigos-profesiones.json
├── src/models/divicion-politico-territorial.json
└── termux/                     # esta versión
```

## Uso

```bash
cd sistema-T
python termux/main.py                 # bucle continuo por micrófono
python termux/main.py --segundos 4    # bloques de 4 segundos
python termux/main.py --file audio.wav  # procesa un archivo (pruebas)
```

La salida muestra, por cada bloque:

```
Reconocido: ingeniero civil
  -> INGENIERO CIVIL [001] (100%) [profesión]

Reconocido: maracaibo santa lucía
  -> Maracaibo Santa Lucía [23, 13, 16] (100%) [ubicación]
     Escribir (cada código con 2 Enters): 23 -> 13 -> 16

Reconocido: libertad
  -> sin coincidencia
     'LIBERTAD' es ambiguo: dicta municipio + parroquia.
```

o `coincidencia débil ... - descartada`.

### Dictado de ubicaciones

- Dicta **municipio + parroquia**: "Maracaibo Santa Lucía" → `23` `13` `16`
  (entidad → municipio → parroquia), cada uno con dos Enters.
- Los **nombres ambiguos** (parroquias repetidas como *Libertad*, *San José*) y
  los **nombres de municipio** no se resuelven solos: hay que dictar ambos.
- Si una parroquia tiene nombre **único** en el estado, sí se puede dictar sola
  (p. ej. "Santa Lucía" o "San Benito").

Salir con **Ctrl+C**.

## Audífonos Bluetooth (micrófono)

`termux-microphone-record` **no permite elegir dispositivo**: graba el micrófono
que Android tenga por defecto. Para dictar con unos auriculares Bluetooth:

1. Empareja los auriculares en Android.
2. Asegúrate de que se use el perfil **HFP / manos libres** (al capturar, Android
   suele activar SCO automáticamente).
3. Si Android sigue usando el micro interno, usa una app de enrutamiento
   (p. ej. *Lesser AudioSwitch*) o los ajustes de desarrollador para seleccionar
   la entrada Bluetooth.
4. Verifica grabando y comprobando que el audio proviene del BT.

Este comportamiento depende del dispositivo Android; no es configurable desde el
código.

## Notas

- Los catálogos deben ser JSON válidos. Si `codigos-profesiones.json` o
  `divicion-politico-territorial.json` tienen errores, la aplicación avisará y no
  arrancará.
- El mensaje debe tener una sola profesión o una ubicación por bloque para una
  coincidencia limpia.
- Los códigos se muestran **tal cual**, conservando los ceros a la izquierda
  ("01", "09").
