import requests
base = "https://sigma.madrid.es/hosted/rest/services/GEOPORTAL/SERVICIO_DE_ESTACIONAMIENTO_REGULADO/MapServer"
r = requests.get(f"{base}/4/query", params={
    "where": "1=1", "outFields": "*", "outSR": 4326,
    "f": "geojson", "resultRecordCount": 5
})
print(r.json()["features"][0]["properties"])
