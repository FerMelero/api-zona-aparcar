# api-zona-aparcar

Mapa de las zonas de estacionamiento regulado (SER) de Madrid: verde, azul, naranja, rojo, etc.

Por ahora es un prototipo que descarga los datos oficiales del Ayuntamiento y los pinta en un mapa. La idea es convertirlo en una API y en una app móvil (PWA) donde se vea de qué color es la zona en la que estás.

## Fuente de datos

Servicio ArcGIS del Ayuntamiento de Madrid (SER):

```
https://sigma.madrid.es/hosted/rest/services/GEOPORTAL/SERVICIO_DE_ESTACIONAMIENTO_REGULADO/MapServer
```

Capas principales:

| Capa | Contenido | Geometría |
|---|---|---|
| 4 | Bandas de aparcamiento (la que usamos) | Líneas |
| 5 | Parquímetros | Puntos |
| 3, 9, 13 | Límite de barrios de la zona SER | Polígonos |
| 14 | Límite de la zona SER | Polígono |
| 55–62 | Zonas de bajas emisiones (ZBE) | Polígonos |

Campos de la capa 4: `Color`, `Bateria_Linea`, `Res_NumPlazas`, `OBJECTID`.

## Contenido

- `test.py`: consulta mínima a la capa 4 (5 registros).
- `descargar.py`: descarga todos los tramos paginando y genera `zonas.geojson` (~87.500 tramos, ~24 MB).
- `mapa.html`: visor Leaflet que pinta `zonas.geojson` por color, con leyenda y popup.

## Uso

```bash
pip install requests
python3 descargar.py          # genera zonas.geojson
python3 -m http.server 8000   # sirve la carpeta
```

Abre http://localhost:8000/mapa.html

## Notas

- El color `Gris` es el más numeroso (~53.000 tramos). Su significado está por confirmar.
- Esta capa no incluye tarifas ni horarios.
- `zonas.geojson` es un archivo generado y pesa 24 MB. Conviene no subirlo al repo (añádelo al `.gitignore`).
- Los datos son orientativos y no sustituyen a la señalización de la calle.

## Siguientes pasos

- [ ] Aclarar el significado de cada color, sobre todo Gris.
- [ ] API (FastAPI) con `GET /zonas?bbox=...` y `GET /zona?lat=..&lon=..`.
- [ ] Caché de los datos con refresco periódico.
- [ ] Frontend PWA con geolocalización.
- [ ] Tarifas y horarios.

## Licencia y datos

Datos del Ayuntamiento de Madrid. Revisa las condiciones de uso del portal de datos abiertos antes de publicar.
