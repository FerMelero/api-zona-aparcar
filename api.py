import json
import time
from contextlib import asynccontextmanager
from pathlib import Path

import requests
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pyproj import Transformer
from shapely import STRtree, box, points
from shapely.geometry import shape
from shapely.ops import transform

AQUI = Path(__file__).parent
MAX_TRAMOS = 20000
PHOTON = "https://photon.komoot.io/api/"
ROUTING_PIE = "https://routing.openstreetmap.de/routed-foot/table/v1/foot/"
PHOTON_UA = "api-zona-aparcar/0.1 (proyecto personal)"
MADRID_BBOX = "-3.95,40.30,-3.45,40.60"  # minLon,minLat,maxLon,maxLat
CACHE_TTL = 3600
cache_busqueda = {}  # (q, lat, lon) -> (instante, resultados)

datos = {}


@asynccontextmanager
async def lifespan(app):
    fichero = AQUI / "zonas.geojson"
    if not fichero.exists():
        raise RuntimeError("Falta zonas.geojson: ejecuta primero python3 descargar.py")
    features = json.loads(fichero.read_text())["features"]
    # Proyección métrica (ETRS89 / UTM 30N) para medir distancias en metros
    a_metros = Transformer.from_crs(4326, 25830, always_xy=True).transform
    geoms = [shape(f["geometry"]) for f in features]
    datos["features"] = features
    datos["arbol"] = STRtree(geoms)
    datos["arbol_m"] = STRtree([transform(a_metros, g) for g in geoms])
    datos["a_metros"] = a_metros
    datos["a_lonlat"] = Transformer.from_crs(25830, 4326, always_xy=True).transform
    yield


app = FastAPI(title="API zonas de aparcamiento Madrid", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["GET"])


@app.get("/zonas")
def zonas(
    bbox: str = Query(..., description="minLon,minLat,maxLon,maxLat"),
    incluir_gris: bool = True,
):
    """GeoJSON de los tramos que caen dentro del área visible."""
    try:
        min_lon, min_lat, max_lon, max_lat = (float(x) for x in bbox.split(","))
    except ValueError:
        raise HTTPException(422, "bbox debe ser minLon,minLat,maxLon,maxLat")
    idx = datos["arbol"].query(box(min_lon, min_lat, max_lon, max_lat))
    feats = [datos["features"][i] for i in sorted(idx)]
    if not incluir_gris:
        feats = [f for f in feats if f["properties"]["Color"] != "Gris"]
    if len(feats) > MAX_TRAMOS:
        raise HTTPException(413, f"Demasiados tramos ({len(feats)}): acerca el mapa")
    return {"type": "FeatureCollection", "features": feats}


@app.get("/zona")
def zona(lat: float, lon: float, radio: float = Query(40, gt=0, le=500)):
    """Color del tramo más cercano a un punto, y colores en un radio (metros)."""
    x, y = datos["a_metros"](lon, lat)
    punto = points(x, y)
    arbol = datos["arbol_m"]
    cercanos = arbol.query(punto.buffer(radio), predicate="intersects")
    if len(cercanos) == 0:
        return {"lat": lat, "lon": lon, "radio_m": radio, "encontrado": False,
                "mensaje": "No hay tramos catalogados cerca de este punto"}
    dist = sorted((punto.distance(arbol.geometries[i]), int(i)) for i in cercanos)
    d0, i0 = dist[0]
    props = datos["features"][i0]["properties"]
    colores = {}
    for d, i in dist:
        c = datos["features"][i]["properties"]["Color"] or "Sin color"
        colores[c] = colores.get(c, 0) + 1
    return {"lat": lat, "lon": lon, "radio_m": radio, "encontrado": True,
            "mas_cercano": {"color": props["Color"], "tipo": props["Bateria_Linea"],
                            "plazas": props["Res_NumPlazas"], "distancia_m": round(d0, 1)},
            "colores_en_radio": colores}


@app.get("/buscar")
def buscar(q: str = Query(..., min_length=3, max_length=100),
           lat: float | None = None, lon: float | None = None, limit: int = Query(5, ge=1, le=10)):
    """Busca calles y sitios de Madrid con Photon. Devuelve lat/lon y una etiqueta legible."""
    clave = (q.strip().lower(), round(lat, 2) if lat is not None else None,
             round(lon, 2) if lon is not None else None, limit)
    ahora = time.time()
    if clave in cache_busqueda and ahora - cache_busqueda[clave][0] < CACHE_TTL:
        return cache_busqueda[clave][1]
    params = {"q": q, "limit": limit, "bbox": MADRID_BBOX}
    if lat is not None and lon is not None:
        params |= {"lat": lat, "lon": lon}
    try:
        r = requests.get(PHOTON, params=params, headers={"User-Agent": PHOTON_UA}, timeout=8)
        r.raise_for_status()
        feats = r.json()["features"]
    except (requests.RequestException, ValueError, KeyError):
        raise HTTPException(502, "El servicio de búsqueda no responde, inténtalo de nuevo")
    resultados = []
    for f in feats:
        p = f["properties"]
        via = p.get("street")
        nombre = p.get("name") or via or ""
        if via and p.get("housenumber"):
            via = f"{via}, {p['housenumber']}"
        primeras = [via] if via and nombre == p.get("street") else [nombre, via]
        partes = [x for x in primeras if x] + [x for x in (p.get("district"), p.get("city")) if x]
        resultados.append({"nombre": nombre, "etiqueta": ", ".join(dict.fromkeys(partes)),
                           "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]})
    cache_busqueda[clave] = (ahora, resultados)
    return resultados


def distancias_a_pie(lon, lat, opciones):
    """Distancia andando (m) desde el punto hasta cada opción, o None si el servicio falla."""
    if not opciones:
        return []
    coords = ";".join([f"{lon},{lat}"] + [f"{o['lon']},{o['lat']}" for o in opciones])
    try:
        r = requests.get(ROUTING_PIE + coords, params={"sources": 0, "annotations": "distance"},
                         headers={"User-Agent": PHOTON_UA}, timeout=6)
        r.raise_for_status()
        fila = r.json()["distances"][0][1:]
        return [round(d) if d is not None else None for d in fila]
    except (requests.RequestException, ValueError, KeyError, IndexError):
        return [None] * len(opciones)


@app.get("/cerca")
def cerca(lat: float, lon: float, radio: float = Query(300, gt=0, le=1000),
          incluir_gris: bool = False):
    """Para cada color, el tramo más cercano al punto (distancia en línea recta) con su punto medio."""
    x, y = datos["a_metros"](lon, lat)
    punto = points(x, y)
    arbol = datos["arbol_m"]
    mejores = {}
    for i in arbol.query(punto.buffer(radio), predicate="intersects"):
        props = datos["features"][i]["properties"]
        color = props["Color"] or "Sin color"
        if color == "Gris" and not incluir_gris:
            continue
        g = arbol.geometries[i]
        d = punto.distance(g)
        if d <= radio and (color not in mejores or d < mejores[color][0]):
            mejores[color] = (d, g, props)
    opciones = []
    for color, (d, g, props) in sorted(mejores.items(), key=lambda kv: kv[1][0]):
        mx, my = g.interpolate(0.5, normalized=True).coords[0]
        mlon, mlat = datos["a_lonlat"](mx, my)
        opciones.append({"color": color, "tipo": props["Bateria_Linea"], "plazas": props["Res_NumPlazas"],
                         "distancia_m": round(d), "lat": round(mlat, 6), "lon": round(mlon, 6)})
    a_pie = distancias_a_pie(lon, lat, opciones)
    for o, d in zip(opciones, a_pie):
        o["a_pie_m"] = d
        o["a_pie_min"] = round(d / 80) if d is not None else None  # ~4,8 km/h
    # Si hay ruta a pie, ordena por ella; si no, por distancia en línea recta
    opciones.sort(key=lambda o: o["a_pie_m"] if o["a_pie_m"] is not None else o["distancia_m"])
    return {"lat": lat, "lon": lon, "radio_m": radio, "opciones": opciones}


@app.get("/")
def inicio():
    return FileResponse(AQUI / "mapa.html")
