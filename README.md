# Pescritura

Aplicacion de escritorio para escribir novelas, organizar mundos y exportar la obra a PDF.

## Requisitos

- Python 3.13+
- PyQt6

## Ejecucion

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python main.py
```

## Que hace

- Gestiona una biblioteca local de obras dentro de `library/`.
- Edita capitulos, notas, fichas de personajes, lugares y mundo.
- Guarda imagenes importadas junto a cada obra.
- Exporta la novela a PDF con portada, indice, capitulos y apendice de mundo opcional.
- Exporta tambien un CSV con la estructura completa de la obra para respaldo o migracion.
- Importa ese CSV para reconstruir una obra nueva en `library/`.
- Crea respaldos ZIP locales por obra.

## Datos locales

La app guarda todo en esta carpeta del proyecto:

- `library/`: obras, manuscritos, notas, fichas, imagenes y respaldos.
- `exports/`: PDFs generados.
- `.venv/`: entorno virtual local.

Esas rutas estan ignoradas por Git para no subir informacion personal ni contenido creado en la app.

## Pruebas

```bash
.venv/bin/python -m unittest discover -s tests -q
```

## Licencia

Apache 2.0. Ver `LICENSE`.
