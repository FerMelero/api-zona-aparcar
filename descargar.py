import json
import requests

BASE = "https://sigma.madrid.es/hosted/rest/services/GEOPORTAL/SERVICIO_DE_ESTACIONAMIENTO_REGULADO/MapServer"
CAPA_BANDAS = 4
PAGINA = 1000


def descargar_capa(capa):
    features, offset = [], 0
    while True:
        r = requests.get(f"{BASE}/{capa}/query", params={
            "where": "1=1", "outFields": "*", "outSR": 4326, "f": "geojson",
            "resultOffset": offset, "resultRecordCount": PAGINA,
        }, timeout=60)
        r.raise_for_status()
        lote = r.json()["features"]
        features += lote
        print(f"capa {capa}: {len(features)} features")
        if len(lote) < PAGINA:
            return features
        offset += PAGINA


if __name__ == "__main__":
    feats = descargar_capa(CAPA_BANDAS)
    with open("zonas.geojson", "w") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
