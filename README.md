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
- `api.py`: API FastAPI que sirve los tramos y el mapa.
- `mapa.html`: visor Leaflet que consume la API: pinta los tramos por color, con leyenda y popup, tiene un botón de geolocalización y un buscador de calles y sitios con enlaces a Google Maps y Waze.

## Uso

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python descargar.py              # genera zonas.geojson
.venv/bin/uvicorn api:app --port 8001      # API + mapa
```

Abre http://localhost:8001 y pulsa **¿Dónde estoy?** para ver el color de la zona en la que estás. Documentación interactiva de la API en http://localhost:8001/docs.

## API

| Endpoint | Descripción |
|---|---|
| `GET /zonas?bbox=minLon,minLat,maxLon,maxLat` | GeoJSON de los tramos dentro del área. Parámetro opcional `incluir_gris=false`. Devuelve 413 si hay más de 20.000 tramos. |
| `GET /zona?lat=..&lon=..&radio=40` | Color del tramo más cercano y recuento de colores en el radio (metros, máx. 500). |
| `GET /buscar?q=..&lat=..&lon=..` | Busca calles y sitios de Madrid con [Photon](https://photon.komoot.io) (OSM, sin clave). Caché de 1 h. Los parámetros `lat`/`lon` priorizan resultados cercanos. |
| `GET /cerca?lat=..&lon=..&radio=300` | Para cada color, el tramo más cercano al punto: distancia en línea recta y andando (ruta a pie vía routing.openstreetmap.de, con respaldo si falla), plazas y coordenadas de su punto medio. Parámetro opcional `incluir_gris`. |

Ejemplo:

```bash
curl "localhost:8001/zona?lat=40.43&lon=-3.687&radio=100"
```

## Notas

- El buscador usa el servicio público de Photon, sin garantías de disponibilidad. Respeta su uso razonable (hay debounce en el frontend y caché en la API).
- Las plazas son la capacidad del tramo, no las libres.
- El color `Gris` es el más numeroso (~53.000 tramos). Su significado está por confirmar.
- Esta capa no incluye tarifas ni horarios.
- `zonas.geojson` es un archivo generado y pesa 24 MB. Conviene no subirlo al repo (añádelo al `.gitignore`).
- Los datos son orientativos y no sustituyen a la señalización de la calle.

## Siguientes pasos

- [x] Distancia andando y filtro por color en el panel.
- [ ] Aclarar el significado de cada color, sobre todo Gris.
- [ ] Caché de los datos con refresco periódico.
- [ ] Convertir el frontend en PWA instalable.
- [ ] Despliegue (el GPS del navegador exige HTTPS fuera de localhost).
- [ ] Tarifas y horarios.

## Licencia y datos

Datos del Ayuntamiento de Madrid. Revisa las condiciones de uso del portal de datos abiertos antes de publicar.
