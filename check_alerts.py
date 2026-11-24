import os
import json
import smtplib
import requests
from email.message import EmailMessage

LEVEL_MAP = {
    "verde": 0, "nessuna": 0, "0": 0,
    "gialla": 1, "ordinaria": 1, "1": 1,
    "arancione": 2, "moderata": 2, "2": 2,
    "rossa": 3, "elevata": 3, "3": 3
}

LEVEL_LABELS = {0: "🟢 VERDE", 1: "🟡 GIALLA", 2: "🟠 ARANCIONE", 3: "🔴 ROSSA"}

def parse_level(val):
    if not val:
        return 0
    s = str(val).lower()
    for k, v in LEVEL_MAP.items():
        if k in s:
            return v
    return 0

def send_ntfy(title, message, priority="default"):
    topic = os.getenv("NTFY_TOPIC")
    if not topic:
        return
    requests.post(
        f"https://ntfy.sh{topic}",
        data=message.encode("utf-8"),
        headers={"Title": title.encode("utf-8"), "Priority": priority, "Tags": "warning"}
    )

def send_email(subject, body):
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    to_addr = os.getenv("EMAIL_TO")
    if not (user and password and to_addr):
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)
    with smtplib.SMTP_SSL("://gmail.com", 465) as smtp:
        smtp.login(user, password)
        smtp.send_message(msg)

def main():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    state_file = "last_state.json"
    if os.path.exists(state_file):
        with open(state_file, "r", encoding="utf-8") as f:
            last_state = json.load(f)
    else:
        last_state = {}

    # Recupera l'ultimo bollettino JSON dal repository DPC
    api_url = "https://github.com"
    files = requests.get(api_url).json()
    latest_json_url = [f["download_url"] for f in files if f["name"].endswith(".json")][-1]
    bollettino = requests.get(latest_json_url).json()

    # Indicizza i dati del bollettino per codice zona
    zone_data = {}
    features = bollettino.get("features", bollettino if isinstance(bollettino, list) else [])
    for item in features:
        props = item.get("properties", item)
        z_cod = props.get("Zona_all") or props.get("ZONA_ALL")
        if z_cod:
            zone_data[z_cod] = props

    new_state = {}
    min_level = config.get("min_level", 1)

    for sub in config["subscriptions"]:
        z_cod = sub["zona_cod"]
        comune = sub["comune"]
        props = zone_data.get(z_cod)
        if not props:
            continue

        # Controlla i rischi principali (Idrogeologico, Idraulico, Temporali)
        rischi = {
            "Idrogeologico": parse_level(props.get("Idrogeo") or props.get("IDROGEO")),
            "Idraulico": parse_level(props.get("Idraulico") or props.get("IDRAULICO")),
            "Temporali": parse_level(props.get("Temporali") or props.get("TEMPORALI"))
        }
        max_lvl = max(rischi.values())
        state_key = f"{sub['istat']}_{z_cod}"
        state_signature = f"{max_lvl}_{rischi}"
        new_state[state_key] = state_signature

        # Invia alert solo se supera la soglia ed è cambiato rispetto all'ultimo invio
        if max_lvl >= min_level and last_state.get(state_key) != state_signature:
            dettagli = "\n".join([f"- {k}: {LEVEL_LABELS[v]}" for k, v in rischi.items() if v > 0])
            titolo = f"Allerta Protezione Civile: {comune} ({LEVEL_LABELS[max_lvl]})"
            corpo = f"Zona di allerta: {z_cod}\nComune: {comune} ({sub['provincia']})\n\nCriticità rilevate:\n{dettagli}"
            
            prio = "urgent" if max_lvl >= 3 else ("high" if max_lvl == 2 else "default")
            send_ntfy(titolo, corpo, priority=prio)
            send_email(titolo, corpo)
            print(f"Alert inviato per {comune}")

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(new_state, f, indent=2)

if __name__ == "__main__":
    main()
