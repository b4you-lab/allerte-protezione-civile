import json
import os
import sys
import requests
from datetime import datetime

SUPABASE_URL = "https://pkaygmgqdbnajsfjjwxj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InBrYXlnbWdxZGJuYWpzZmpqd3hqIiwicm9sZSI6ImFub24iLCJpYXQiOjE3OTU2MjgwODQsImV4cCI6MjExMTIwNDA4NH0.XJgDZ1voMOHDG0iisIWgcLVkW4sKKTMpLWVsBH0A1CE"
API_BASE = "https://allertameteo.app/api"

# Header per evitare blocchi da parte dell'API
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

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
        print(f"✅ Notifica inviata con successo su topic: {topic}")
    except Exception as e:
        print(f"❌ Errore invio notifica a {topic}: {e}")

def carica_stato():
    """Carica lo stato precedente proteggendosi da file vuoti o corrotti"""
    if os.path.exists('stato_precedente.json') and os.path.getsize('stato_precedente.json') > 0:
        try:
            with open('stato_precedente.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"File stato_precedente.json non valido ({e}), inizializzo a vuoto.")
            return {}
    return {}

def salva_stato(stato):
    with open('stato_precedente.json', 'w', encoding='utf-8') as f:
        json.dump(stato, f, indent=2, ensure_ascii=False)

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
    """Estrae il livello (0: Verde, 1: Gialla, 2: Arancione, 3: Rossa)"""
    try:
        payload = dati.get("data", dati)
        oggi = payload.get("oggi", {})
        allerta = oggi.get("allerta", {})
        colore = str(allerta.get("colore", "")).lower()
        
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
    print(f"--- Controllo Allerte Protezione Civile ---")
    print(f"Data/Ora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    try:
        iscrizioni = leggi_iscrizioni()
        print(f"Trovate {len(iscrizioni)} iscrizioni su Supabase.")
    except Exception as e:
        print(f"❌ Errore durante la lettura da Supabase: {e}")
        sys.exit(1)

    if not iscrizioni:
        print("Nessuna iscrizione attiva nel database. Termino.")
        return

    # Raggruppa i topic per comune
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
        print(f"\nVerifica comune: '{comune}' (topic collegati: {topics})")
        try:
            url = f"{API_BASE}/alert/{requests.utils.quote(comune)}"
            r = requests.get(url, headers=HEADERS, timeout=15)
            r.raise_for_status()
            dati = r.json()

            livello = estrai_livello(dati)
            livello_precedente = stato_precedente.get(comune, 0)
            stato_attuale[comune] = livello

            colori_nome = {0: "VERDE (Nessuna allerta)", 1: "GIALLA 🟡", 2: "ARANCIONE 🟠", 3: "ROSSA 🔴"}
            print(f"  -> Stato rilevato: {colori_nome.get(livello, 'Sconosciuto')}")

            # Se c'è un'allerta attiva ed è cambiata rispetto allo stato precedente
            if livello >= 1 and livello != livello_precedente:
                msg = f"🚨 Allerta {colori_nome.get(livello)}\nComune: {comune}\nControlla gli aggiornamenti della Protezione Civile."
                for topic in topics:
                    notifiche.append((topic, msg))
            else:
                if livello == 0:
                    print(f"  -> Nessuna notifica necessaria (livello verde).")
                else:
                    print(f"  -> Livello invariato rispetto al controllo precedente ({livello_precedente}), nessuna nuova notifica inviata.")

        except Exception as e:
            print(f"❌ Errore durante il controllo del comune '{comune}': {e}")
            if comune in stato_precedente:
                stato_attuale[comune] = stato_precedente[comune]

    # Invia notifiche
    if notifiche:
        print(f"\nInvio di {len(notifiche)} notifiche in corso...")
        for topic, msg in notifiche:
            invia_notifica_ntfy(topic, msg)
    else:
        print("\nNessuna nuova notifica da inviare in questa esecuzione.")

    salva_stato(stato_attuale)
    print("\nControllo completato con successo.")

if __name__ == "__main__":
    main()
