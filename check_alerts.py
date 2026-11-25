import asyncio
import json
import os
import sys
from datetime import datetime

from aiodpc import AlertLevel, DpcClient, DpcError

# Coordinate di Levico Terme (dalla pagina allertameteo.app: 46.01667, 11.3)
LEVICO_TERME = (46.01667, 11.3)

def invia_notifica(messaggio):
    token = os.getenv("TELEGRAM_TOKEN")
    chat_id = os.getenv("CHAT_ID")
    if not token or not chat_id:
        print("Credenziali Telegram mancanti. Salto notifica.")
        return
    
    import requests
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

async def main():
    print(f"Controllo del {datetime.now().isoformat()}")
    
    with open('config.json', 'r') as f:
        config = json.load(f)
    
    min_level = config.get('min_level', 1)  # 1 = Gialla, 2 = Arancione, 3 = Rossa
    zone_da_monitorare = {sub['zona_cod']: sub['comune'] for sub in config.get('subscriptions', [])}
    
    # Mappa dei livelli aiodpc -> numerico per confronto con min_level
    livello_numerico = {
        AlertLevel.GREEN: 0,
        AlertLevel.YELLOW: 1,
        AlertLevel.ORANGE: 2,
        AlertLevel.RED: 3,
    }
    livello_testo = {1: "Gialla", 2: "Arancione", 3: "Rossa"}

    stato_precedente = carica_stato()
    stato_attuale = {}
    messaggi_alert = []

    try:
        async with DpcClient() as client:
            # Recupera il bollettino di criticità per Levico Terme
            criticality = await client.get_criticality(
                LEVICO_TERME[0], LEVICO_TERME[1],
                municipality="Levico Terme"
            )
            
            # La zona di allerta restituita da aiodpc per Levico Terme
            # (il codice TAA-A nel tuo config.json corrisponde a questa zona)
            codice_zona = "TAA-A"  # manteniamo il codice del config per coerenza
            
            if codice_zona in zone_da_monitorare:
                # Controlla il livello di oggi
                oggi = criticality.today()
                if oggi:
                    livello_raw = livello_numerico.get(oggi.max_level, 0)
                    
                    if livello_raw >= min_level:
                        stato_attuale[codice_zona] = livello_raw
                        nome_comune = zone_da_monitorare[codice_zona]
                        
                        if stato_precedente.get(codice_zona) != livello_raw:
                            messaggi_alert.append(
                                f"🚨 <b>Allerta Protezione Civile</b>\n"
                                f"Comune: <b>{nome_comune}</b>\n"
                                f"Zona: {codice_zona}\n"
                                f"Livello: <b>{livello_testo.get(livello_raw, 'Sconosciuto')}</b>\n"
                                f"Data: {oggi.date}"
                            )
                    else:
                        stato_attuale[codice_zona] = 0
                else:
                    print("Nessun dato per oggi disponibile.")
                    stato_attuale[codice_zona] = 0
                    
    except DpcError as err:
        print(f"Errore DPC: {err}")
        sys.exit(1)
    except Exception as e:
        print(f"Errore imprevisto: {e}")
        sys.exit(1)

    for msg in messaggi_alert:
        invia_notifica(msg)

    salva_stato(stato_attuale)
    print(f"Controllo completato. {len(messaggi_alert)} nuovi alert rilevati.")

if __name__ == "__main__":
    asyncio.run(main())
