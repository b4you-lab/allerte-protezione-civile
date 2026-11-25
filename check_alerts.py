import json
import csv
import io
import requests
import os
import sys
from datetime import datetime 

# ... (le tue funzioni invia_notifica, carica_stato, salva_stato rimangono uguali) ...

def main():
    print(f"Controllo del {datetime.now().isoformat()}")
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    min_level = config.get('min_level', 1)
    subscriptions = config.get('subscriptions', [])
    zone_da_monitorare = { sub['zona_cod']: sub['comune'] for sub in subscriptions }

    # NUOVO URL (CSV)
    URL_BOLLETTINO = "https://raw.githubusercontent.com/opendatasicilia/DPC-bollettini-criticita-idrogeologica-idraulica/master/oggi/bollettino-oggi-zone-latest.csv"

    try:
        response = requests.get(URL_BOLLETTINO, timeout=15)
        response.raise_for_status()
        # Leggiamo il CSV
        csv_content = response.text
    except Exception as e:
        print(f"Errore nel download del bollettino: {e}")
        sys.exit(1)

    stato_precedente = carica_stato()
    stato_attuale = {}
    messaggi_alert = []

    # Mappa dei livelli (adattata ai valori testuali del CSV)
    # Esempio: "ALLERTA GIALLA" -> 1, "ALLERTA ARANCIONE" -> 2, "ALLERTA ROSSA" -> 3
    def get_livello(testo):
        if not testo: return 0
        testo = testo.upper()
        if "ROSSA" in testo: return 3
        if "ARANCIONE" in testo: return 2
        if "GIALLA" in testo: return 1
        return 0

    # Analizziamo il CSV
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
                
                if stato_precedente.get(codice_zona) != livello_raw:
                    livelli_map = {1: "Gialla", 2: "Arancione", 3: "Rossa"}
                    messaggi_alert.append(
                        f"🚨 <b>Allerta Protezione Civile</b>\n"
                        f"Comune: <b>{nome_comune}</b>\n"
                        f"Zona: {codice_zona}\n"
                        f"Livello: <b>{livelli_map.get(livello_raw, 'Sconosciuto')}</b>"
                    )
            else:
                stato_attuale[codice_zona] = 0

    for msg in messaggi_alert:
        invia_notifica(msg)

    salva_stato(stato_attuale)
    print(f"Controllo completato. {len(messaggi_alert)} nuovi alert rilevati.")

if __name__ == "__main__":
    main()
