import json
import os
import sys
import requests
from datetime import datetime

SUPABASE_URL = "https://pkaygmgqdbnajsfjjwxj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBrYXlnbWdxZGJuYWpzZmpqd3hqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTU2MjgwODQsImV4cCI6MjExMTIwNDA4NH0.XJgDZ1voMOHDG0iisIWgcLVkW4sKKTMpLWVsBH0A1CE"
API_BASE = "https://allertameteo.app/api"

def invia_notifica_ntfy(topic, messaggio, titolo="Allerta Protezione Civile"):
    url = f"https://ntfy.sh/{topic}"
    headers = {
        "Title": titolo,
        "Priority": "high",
        "Tags": "warning"
    }
    try:
        r = requests.post(url, data=messaggio.encode("utf-8"), headers=headers, timeout=10)
        r.raise_for_status()
        print(f"Notifica inviata a {topic}")
    except Exception as e:
        print(f"Errore invio ntfy a {topic}: {e}")

def carica_stato():
    if os.path.exists('stato_precedente.json'):
        with open('stato_precedente.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def salva_stato(stato):
    with open('stato_precedente.json', 'w', encoding='utf-8') as f:
        json.dump(stato, f, indent=2)

def leggi_iscrizioni():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}"
    }
    url = f"{SUPABASE_URL}/rest/v1/iscrizioni?select=ntfy_topic,comune"
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()

def estrai_livello(dati):
    """Estrae il livello (0: Verde/Nessuna, 1: Gialla, 2: Arancione, 3: Rossa)"""
    try:
        payload = dati.get("data", dati)
        oggi = payload.get("oggi", {})
        allerta = oggi.get("allerta", {})
        colore = allerta.get("colore", "").lower()
        
        if "rosso" in colore or "rossa" in colore:
            return 3
        elif "arancione" in colore:
            return 2
        elif "giallo" in colore or "gialla" in colore:
            return 1
        return 0
    except Exception:
        return 0

def main():
    print(f"Controllo allerte avviato: {datetime.now().isoformat()}")

    try:
        iscrizioni = leggi_iscrizioni()
    except Exception as e:
        print(f"Errore lettura Supabase: {e}")
        sys.exit(1)

    if not iscrizioni:
        print("Nessuna iscrizione trovata nel database.")
        return

    comuni = {}
    for isc in iscrizioni:
        comune = isc.get('comune')
        topic = isc.get('ntfy_topic')
        if comune and topic:
            comuni.setdefault(comune, []).append(topic)

    stato_precedente = carica_stato()
    stato_attuale = {}
    notifiche = []

    for comune, topics in comuni.items():
        try:
            # Endpoint corretto con path param
            url = f"{API_BASE}/alert/{requests.utils.quote(comune)}"
            r = requests.get(url, timeout=15)
            r.raise_for_status()
            dati = r.json()

            livello = estrai_livello(dati)
            stato_attuale[comune] = livello
            livello_precedente = stato_precedente.get(comune, 0)

            # Invia solo se c'è allerta (>= 1) ed è cambiata
            if livello >= 1 and livello != livello_precedente:
                colori = {1: "GIALLA 🟡", 2: "ARANCIONE 🟠", 3: "ROSSA 🔴"}
                msg = f"🚨 Allerta {colori.get(livello, '')} per {comune}!\nConsulta le indicazioni del tuo comune."
                for topic in topics:
                    notifiche.append((topic, msg))

        except Exception as e:
            print(f"Errore controllo per '{comune}': {e}")
            if comune in stato_precedente:
                stato_attuale[comune] = stato_precedente[comune]

    for topic, msg in notifiche:
        invia_notifica_ntfy(topic, msg)

    salva_stato(stato_attuale)
    print(f"Controllo completato. Notifiche inviate: {len(notifiche)}.")

if __name__ == "__main__":
    main()
