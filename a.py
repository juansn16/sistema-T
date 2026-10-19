import pandas as pd
import json

# 1. Cargar la primera hoja del archivo Excel
# dtype={'COD': str} asegura que los códigos mantengan los ceros a la izquierda (ej. "008")
df = pd.read_excel('PROFESIONES.xlsx', sheet_name=0, dtype={'COD': str})

# 2. Crear un diccionario donde la clave sea la PROFESIÓN y el valor sea el CÓDIGO
# Invertimos el orden: dict(zip(PROFESION, COD))
diccionario_inverso = dict(zip(df['PROFESION U OFICIO'], df['COD']))

# 3. Guardar el resultado en un archivo JSON
with open('resultado_profesion_codigo.json', 'w', encoding='utf-8') as f:
    json.dump(diccionario_inverso, f, ensure_ascii=False, indent=4)

print("¡JSON de Profesión -> Código generado con éxito!")