import json
import time
import requests
import geopandas as gpd
from shapely.geometry import Point

HOST_RAW = "https://" + "raw." + "githubusercontent.com"
HOST_API = "https://" + "api." + "github.com"

def fetch_json(url, retries=5):
    for i in range(retries):
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(5)

print("1. Scaricamento comuni italiani...")
comuni_url = HOST_RAW + "/matteocontrini/comuni-json/master/comuni.json"
comuni_data = fetch_json(comuni_url)

print("2. Recupero ultimo bollettino DPC per i confini delle zone...")
api_url = HOST_API + "/repos/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/contents/files"
files = fetch_json(api_url)
json_files = sorted([f for f in files if f["name"].endswith(".json")], key=lambda x: x["name"])
latest_meta = fetch_json(json_files[-1]["download_url"])

topo_url = latest_meta["topo_json"]["today"]
gdf_zone = gpd.read_file(topo_url)
if gdf_zone.crs is None:
    gdf_zone = gdf_zone.set_crs(epsg=4326)
else:
    gdf_zone = gdf_zone.to_crs(epsg=4326)

print("3. Scaricamento coordinate comuni...")
coord_url = HOST_RAW + "/opendatasicilia/comuni-italiani/main/dati/comuni.json"
coord_list = fetch_json(coord_url)
coord_map = {str(c["pro_com_t"]).zfill(6): (float(c["long"]), float(c["lat"])) for c in coord_list if c.get("lat")}

output = []
for c in comuni_data:
    codice = c["codice"]
    if codice not in coord_map:
        continue
    lon, lat = coord_map[codice]
    punto = Point(lon, lat)
    
    match = gdf_zone[gdf_zone.contains(punto)]
    if match.empty:
        distanze = gdf_zone.distance(punto)
        zona_row = gdf_zone.loc[distanze.idxmin()]
    else:
        zona_row = match.iloc[0]

    zona_cod = str(zona_row.get("Zona_all") or zona_row.get("ZONA_ALL") or zona_row.iloc[0])
    zona_nome = str(zona_row.get("Nome_zona") or zona_row.get("NOME_ZONA") or zona_cod)

    output.append({
        "regione": c["regione"]["nome"],
        "provincia": c["provincia"]["nome"],
        "sigla": c["sigla"],
        "comune": c["nome"],
        "istat": codice,
        "zona_cod": zona_cod,
        "zona_nome": zona_nome
    })

with open("comuni_zone.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"Generato comuni_zone.json con {len(output)} comuni.")
