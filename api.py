import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pyproj import Transformer
from shapely import STRtree, box, points
from shapely.geometry import shape
from shapely.ops import transform

AQUI = Path(__file__).parent
MAX_TRAMOS = 20000

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


@app.get("/")
def inicio():
    return FileResponse(AQUI / "mapa.html")
