import json
import os
import sys
import requests
from datetime import datetime

# === CONFIGURAZIONE SUPABASE ===
SUPABASE_URL = "https://pkaygmgqdbnajsfjjwxj.supabase.co"
SUPABASE_KEY = "sb_publishable_f66hmlBUBDmNrrWk64_vSQ_6PqNr5kZ"
# ===============================

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
        print(f"Notifica ntfy inviata a {topic}")
    except Exception as e:
        print(f"Errore invio ntfy a {topic}: {e}")

def carica_stato():
    if os.path.exists('stato_precedente.json'):
        with open('stato_precedente.json', 'r') as f:
            return json.load(f)
    return {}

def salva_stato(stato):
    with open('stato_precedente.json', 'w') as f:
        json.dump(stato, f)

def leggi_iscrizioni():
    # CORREZIONE: Usiamo solo l'header 'apikey' senza 'Authorization: Bearer'
    headers = {
        "apikey": SUPABASE_KEY
    }
    url = f"{SUPABASE_URL}/rest/v1/iscrizioni?select=ntfy_topic,comune"
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()

def main():
    print(f"Controllo del {datetime.now().isoformat()}")

    try:
        iscrizioni = leggi_iscrizioni()
    except Exception as e:
        print(f"Errore lettura Supabase: {e}")
        sys.exit(1)

    if not iscrizioni:
        print("Nessuna iscrizione trovata.")
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
            r = requests.get(f"{API_BASE}/alert", params={"comune": comune}, timeout=15)
            r.raise_for_status()
            dati = r.json()

            livello = 0
            if isinstance(dati, dict):
                for key in ['level', 'livello', 'allerta']:
                    if key in dati:
                        val = dati[key]
                        if isinstance(val, str):
                            val = val.lower()
                            if 'rossa' in val: livello = 3
                            elif 'arancione' in val: livello = 2
                            elif 'gialla' in val: livello = 1
                        elif isinstance(val, (int, float)):
                            livello = int(val)
                        break
            elif isinstance(dati, list):
                for item in dati:
                    for key in ['level', 'livello']:
                        if key in item:
                            val = item[key]
                            if isinstance(val, str):
                                val = val.lower()
                                if 'rossa' in val: livello = max(livello, 3)
                                elif 'arancione' in val: livello = max(livello, 2)
                                elif 'gialla' in val: livello = max(livello, 1)
                            elif isinstance(val, (int, float)):
                                livello = max(livello, int(val))

            stato_attuale[comune] = livello

            if livello >= 1 and stato_precedente.get(comune) != livello:
                livelli_testo = {1: "Gialla", 2: "Arancione", 3: "Rossa"}
                msg = f"🚨 Allerta {livelli_testo.get(livello, '')}\nComune: {comune}"
                for topic in topics:
                    notifiche.append((topic, msg))

        except Exception as e:
            print(f"Errore controllo {comune}: {e}")
            if comune in stato_precedente:
                stato_attuale[comune] = stato_precedente[comune]

    for topic, msg in notifiche:
        invia_notifica_ntfy(topic, msg)

    salva_stato(stato_attuale)
    print(f"Controllo completato. {len(notifiche)} notifiche inviate.")

if __name__ == "__main__":
    main()
