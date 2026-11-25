import os
import json
import time
import requests
import geopandas as gpd

HOST_API = "https://" + "api." + "github.com"
PUBLIC_PREFIX = "b4you-dpc-"

LEVEL_MAP = {
    "verde": 0, "nessuna": 0, "0": 0,
    "gialla": 1, "ordinaria": 1, "1": 1,
    "arancione": 2, "moderata": 2, "2": 2,
    "rossa": 3, "elevata": 3, "3": 3
}
LEVEL_LABELS = {0: "🟢 VERDE", 1: "🟡 GIALLA", 2: "🟠 ARANCIONE", 3: "🔴 ROSSA"}

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

def parse_level(val):
    if not val:
        return 0
    s = str(val).lower()
    for k, v in LEVEL_MAP.items():
        if k in s:
            return v
    return 0

def send_ntfy(topic, title, message, priority="default"):
    if not topic:
        return
    requests.post(
        f"https://ntfy.sh{topic}",
        data=message.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Priority": priority, "Tags": "warning"}
    )

def main():
    state_file = "last_state.json"
    last_state = json.load(open(state_file, "r", encoding="utf-8")) if os.path.exists(state_file) else {}

    api_url = HOST_API + "/repos/pcm-dpc/DPC-Bollettini-Criticita-Idrogeologica-Idraulica/contents/files"
    files = fetch_json(api_url)
    json_files = sorted([f for f in files if f["name"].endswith(".json")], key=lambda x: x["name"])
    latest_meta = fetch_json(json_files[-1]["download_url"])

    gdf_today = gpd.read_file(latest_meta["topo_json"]["today"])
    new_state = {}
    active_alerts = {}

    for _, props in gdf_today.iterrows():
        z_cod = str(props.get("Zona_all") or props.get("ZONA_ALL") or "")
        z_nome = str(props.get("Nome_zona") or props.get("NOME_ZONA") or z_cod)
        if not z_cod:
            continue

        rischi = {
            "Idrogeologico": parse_level(props.get("Idrogeo") or props.get("IDROGEO")),
            "Idraulico": parse_level(props.get("Idraulico") or props.get("IDRAULICO")),
            "Temporali": parse_level(props.get("Temporali") or props.get("TEMPORALI"))
        }
        max_lvl = max(rischi.values())
        sig = f"{max_lvl}_{rischi}"
        new_state[z_cod] = sig

        active_alerts[z_cod] = {
            "zona_cod": z_cod,
            "zona_nome": z_nome,
            "livello": max_lvl,
            "etichetta": LEVEL_LABELS[max_lvl],
            "rischi": {k: LEVEL_LABELS[v] for k, v in rischi.items() if v > 0}
        }

        if max_lvl >= 1 and last_state.get(z_cod) != sig:
            dettagli = "\n".join([f"- {k}: {LEVEL_LABELS[v]}" for k, v in rischi.items() if v > 0])
            titolo = f"Allerta DPC {z_cod} ({LEVEL_LABELS[max_lvl]})"
            corpo = f"Zona: {z_cod} - {z_nome}\n\nCriticità:\n{dettagli}"
            prio = "urgent" if max_lvl >= 3 else ("high" if max_lvl == 2 else "default")

            # Pubblica sul canale pubblico della zona (per tutti gli utenti)
            safe_topic = PUBLIC_PREFIX + z_cod.replace(" ", "_")
            send_ntfy(safe_topic, titolo, corpo, priority=prio)

            # Invia anche sul tuo topic personale se configurato nei Secrets
            personal_topic = os.getenv("NTFY_TOPIC")
            if personal_topic:
                send_ntfy(personal_topic, titolo, corpo, priority=prio)

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2)

    with open("active_alerts.json", "w", encoding="utf-8") as f:
        json.dump({
            "aggiornamento": latest_meta.get("data", ""),
            "zone": active_alerts
        }, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
