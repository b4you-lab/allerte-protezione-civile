import json
import requests
import geopandas as gpd
from shapely.geometry import Point

print("1. Scaricamento comuni italiani...")
comuni_url = "https://githubusercontent.com"
comuni_data = requests.get(comuni_url).json()

print("2. Scaricamento Zone di Allerta Protezione Civile...")
api_url = "https://github.com"
files = requests.get(api_url).json()
geojson_url = [f["download_url"] for f in files if f["name"].endswith(".geojson")][-1]
gdf_zone = gpd.read_file(geojson_url).to_crs(epsg=4326)

print("3. Scaricamento coordinate comuni...")
coord_url = "https://githubusercontent.com"
coord_list = requests.get(coord_url).json()
coord_map = {}
for c in coord_list:
    cod = str(c.get("pro_com_t") or c.get("pro_com", "")).zfill(6)
    if c.get("lat") and c.get("long"):
        coord_map[cod] = (float(c["long"]), float(c["lat"]))

output = []
for c in comuni_data:
    codice = str(c["codice"]).zfill(6)
    if codice not in coord_map:
        continue
    lon, lat = coord_map[codice]
    punto = Point(lon, lat)

    match = gdf_zone[gdf_zone.contains(punto)]
    if match.empty:
        punto_m = gpd.GeoSeries([punto], crs="EPSG:4326").to_crs(epsg=32632).iloc[0]
        distanze = gdf_zone.to_crs(epsg=32632).distance(punto_m)
        zona_row = gdf_zone.loc[distanze.idxmin()]
    else:
        zona_row = match.iloc[0]

    cols = {k.lower(): k for k in gdf_zone.columns}
    first_col = list(cols.values())[0]
    zona_cod = str(zona_row[cols.get("zona_all", first_col)])
    zona_nome = str(zona_row[cols.get("nome_zona", cols.get("zona_all", first_col))])

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

print(f"Completato! Generato comuni_zone.json con {len(output)} comuni.")