import json
import csv
import io
import requests
import os
import sys
from datetime import datetime, timedelta

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

    # 2. Scaricamento dinamico del CSV
    data_oggi = datetime.now().strftime("%Y%m%d")
    URL_BOLLETTINO = f"https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/master/{data_oggi}-bollettino-oggi-zone.csv"

    try:
        print(f"Tentativo download: {URL_BOLLETTINO}")
        response = requests.get(URL_BOLLETTINO, timeout=15)
        response.raise_for_status()
        csv_content = response.text
        print("Download completato con successo (file di oggi).")
    except Exception as e:
        print(f"File di oggi non trovato ({e}). Provo con il file di ieri...")
        data_ieri = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
        URL_BOLLETTINO = f"https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/master/{data_ieri}-bollettino-oggi-zone.csv"
        try:
            response = requests.get(URL_BOLLETTINO, timeout=15)
            response.raise_for_status()
            csv_content = response.text
            print("Download completato con successo (file di ieri).")
        except Exception as e2:
            print(f"Errore critico: impossibile scaricare il bollettino. {e2}")
            sys.exit(1)

    stato_precedente = carica_stato()
    stato_attuale = {}
    messaggi_alert = []

    # Mappa dei livelli (adattata ai valori testuali del CSV)
    def get_livello(testo):
        if not testo: return 0
        testo = testo.upper()
        if "ROSSA" in testo: return 3
        if "ARANCIONE" in testo: return 2
        if "GIALLA" in testo: return 1
        return 0

    livelli_map = {1: "Gialla", 2: "Arancione", 3: "Rossa"}

    # 3. Analizziamo il CSV
    reader = csv.DictReader(io.StringIO(csv_content))
    for row in reader:
        # La colonna della zona nel CSV di opendatasicilia si chiama 'zona_codice'
        codice_zona = row.get('zona_codice')
        
        if codice_zona in zone_da_monitorare:
            # Prendiamo il livello di criticità più alto tra i vari rischi
            livelli = [
                get_livello(row.get('avviso_criticita')),
                get_livello(row.get('avviso_idrogeologico')),
                get_livello(row.get('avviso_temporali')),
                get_livello(row.get('avviso_idraulico'))
            ]
            livello_raw = max(livelli) if livelli else 0
            
            if livello_raw >= min_level:
                stato_attuale[codice_zona] = livello_raw
                nome_comune = zone_da_monitorare[codice_zona]
                
                # Controlla se è un nuovo alert o è cambiato
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
