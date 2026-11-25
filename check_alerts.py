import json
import requests
import os
import sys
from datetime import datetime

# URL del bollettino nazionale DPC (JSON)
URL_BOLLETTINO = "https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/master/bollettino-oggi-zone-latest.csv"

def invia_notifica(messaggio):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id:
        print("Credenziali Telegram mancanti. Salto notifica.")
        return
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": messaggio, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("Notifica inviata.")
    except Exception as e:
        print(f"Errore invio notifica: {e}")

def carica_stato():
    if os.path.exists('stato_precedente.json'):
        with open('stato_precedente.json', 'r') as f:
            return json.load(f)
    return {}

def salva_stato(stato):
    with open('stato_precedente.json', 'w') as f:
        json.dump(stato, f)

def main():
    print(f"Controllo del {datetime.now().isoformat()}")
    
    # 1. Carica la configurazione
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    min_level = config.get('min_level', 1)
    subscriptions = config.get('subscriptions', [])
    
    # Estraiamo le zone da monitorare dal config
    zone_da_monitorare = { sub['zona_cod']: sub['comune'] for sub in subscriptions }

    # 2. Scarica il bollettino
    try:
        response = requests.get(URL_BOLLETTINO, timeout=15)
        response.raise_for_status()
        bollettino = response.json()
    except Exception as e:
        print(f"Errore nel download del bollettino: {e}")
        sys.exit(1)

    stato_precedente = carica_stato()
    stato_attuale = {}
    messaggi_alert = []

    # Mappa dei livelli (es. 0=Verde, 1=Gialla, 2=Arancione, 3=Rossa)
    # Da adattare in base alla struttura esatta del JSON DPC
    livelli_map = {0: "Verde", 1: "Gialla", 2: "Arancione", 3: "Rossa"}

    # 3. Analizza il bollettino
    # Nota: La struttura del JSON DPC potrebbe variare, questo è un esempio logico
    for zona in bollettino.get('zone', []):
        codice_zona = zona.get('codice_zona')
        
        if codice_zona in zone_da_monitorare:
            # Estrai il livello di criticità (adatta la chiave in base al JSON reale)
            livello_raw = zona.get('livello_criticita', 0) 
            
            # Se il livello supera la soglia minima impostata nel config
            if livello_raw >= min_level:
                stato_attuale[codice_zona] = livello_raw
                nome_comune = zone_da_monitorare[codice_zona]
                
                # Controlla se è un nuovo alert
                if stato_precedente.get(codice_zona) != livello_raw:
                    messaggi_alert.append(
                        f"🚨 <b>Allerta Protezione Civile</b>\n"
                        f"Comune: <b>{nome_comune}</b>\n"
                        f"Zona: {codice_zona}\n"
                        f"Livello: <b>{livelli_map.get(livello_raw, 'Sconosciuto')}</b>"
                    )
            else:
                # Se il livello scende sotto la soglia, resettiamo lo stato
                stato_attuale[codice_zona] = 0

    # 4. Invia notifiche
    for msg in messaggi_alert:
        invia_notifica(msg)

    # 5. Salva il nuovo stato
    salva_stato(stato_attuale)
    print(f"Controllo completato. {len(messaggi_alert)} nuovi alert rilevati.")

if __name__ == "__main__":
    main()
