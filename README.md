# DownTube (Python + Vercel)

Aplicacion web en Python para descargar videos de YouTube en el formato/resolucion seleccionados por el usuario.

## Stack

- Backend: Flask
- Descarga/metadata: yt-dlp
- Frontend: HTML + CSS + JS vanilla
- Deploy: Vercel (`@vercel/python`)

## Ejecutar en local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python api/index.py
```

Abre: `http://127.0.0.1:5000`

## Despliegue en Vercel

1. Sube este proyecto a un repositorio Git.
2. Importa el repo en Vercel.
3. Vercel detecta `vercel.json` y desplegara `api/index.py`.
4. No necesitas configurar framework preset.

## Uso

1. Pega la URL de YouTube.
2. Pulsa `Cargar calidades`.
3. Selecciona el formato (resolucion + contenedor + audio).
4. Pulsa `Descargar`.

## Nota importante

- Esta app depende de las limitaciones de Vercel Serverless (tiempo de ejecucion, tamano de respuesta y red).
- Algunos videos pueden no estar disponibles por restricciones regionales, DRM, edad o cambios de YouTube.
- Respeta derechos de autor y terminos de uso al descargar contenido.
