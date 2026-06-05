import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

# NON chiamare logging.basicConfig() qui: la configurazione del logging
# è responsabilità degli script di alto livello (run_static.py, run_dynamic.py).
# Una chiamata basicConfig() a livello di modulo configura il root logger su stderr
# prima che gli orchestratori possano configurarlo su stdout.
logger = logging.getLogger(__name__)

class BaseScraper:
    def __init__(self, config):
        """
        Inizializza lo scraper con le opzioni di configurazione e crea una sessione requests.
        """
        self.config = config
        self.base_url = config.get('base_url', '')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def fetch_page(self, url, params=None, retries=3, backoff=2):
        """
        Scarica una pagina web con meccanismo di retry e la restituisce come oggetto BeautifulSoup.

        In caso di Timeout o ConnectionError definitivo (dopo tutti i tentativi),
        stampa un messaggio chiaro e restituisce None invece di sollevare un'eccezione,
        così l'orchestratore può proseguire con la fonte successiva senza bloccarsi.
        """
        full_url = url if url.startswith('http') else urljoin(self.base_url, url)
        last_exception = None

        for attempt in range(retries):
            try:
                if attempt == 0:
                    logger.info(
                        f"Connessione al server in corso: {full_url}\n"
                        f"         [Attenzione: il server comunale puo' impiegare diversi minuti per rispondere. "
                        f"Il processo NON e' bloccato – attesa risposta HTTP in corso...]"
                    )
                else:
                    logger.info(
                        f"Nuovo tentativo di connessione (retry {attempt} di {retries - 1}): {full_url}"
                    )
                # Timeout esplicito: 120 secondi per pagine molto grandi
                response = self.session.get(full_url, params=params, timeout=120)
                response.raise_for_status()
                response.encoding = 'utf-8' # Forza decodifica corretta
                try:
                    return BeautifulSoup(response.text, 'lxml')
                except Exception:
                    return BeautifulSoup(response.text, 'html.parser')

            except requests.exceptions.Timeout as e:
                last_exception = e
                logger.warning(
                    f"Timeout alla pagina {full_url} (Tentativo {attempt+1}/{retries}). "
                    f"Il server non risponde entro 120 secondi."
                )
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                logger.warning(
                    f"Errore di connessione alla pagina {full_url} (Tentativo {attempt+1}/{retries}): {e}"
                )
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))

            except Exception as e:
                last_exception = e
                logger.warning(
                    f"Errore nel recupero della pagina {full_url}: {e}. "
                    f"Nuovo tentativo tra {backoff * (attempt + 1)}s..."
                )
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                else:
                    # Per errori non di rete (es. HTTP 4xx/5xx), rilancia l'eccezione
                    logger.error(f"Impossibile recuperare la pagina {full_url} dopo {retries} tentativi.")
                    raise e

        # Tutti i tentativi esauriti per Timeout o ConnectionError
        print(
            f"\n[AVVISO RETE] Il server del comune è temporaneamente lento o non risponde. "
            f"Salto la fonte corrente. (URL: {full_url})\n"
        )
        logger.error(
            f"Impossibile connettersi a {full_url} dopo {retries} tentativi. "
            f"Ultima eccezione: {last_exception}"
        )
        return None

    def extract_table(self, soup, row_selector, field_map):
        """
        Extracts a table using selectors and returns a list of dictionaries.
        """
        rows = soup.select(row_selector)
        results = []
        for row in rows:
            record = {}
            for field, selector in field_map.items():
                element = row.select_one(selector)
                if element:
                    record[field] = element.get_text(strip=True)
                else:
                    record[field] = None
            results.append(record)
        return results

    def download_file(self, url, dest_path, retries=3, backoff=2):
        """
        Downloads a file from an URL, saves it to dest_path, creates parent directories if needed,
        and skips downloading if the file already exists.
        """
        if not url:
            logger.warning("Empty URL provided for download.")
            return False

        full_url = url if url.startswith('http') else urljoin(self.base_url, url)

        if os.path.exists(dest_path):
            logger.info(f"File already exists: {dest_path}. Skipping download.")
            return True

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        for attempt in range(retries):
            try:
                logger.info(f"Downloading file from {full_url} to {dest_path} (Attempt {attempt+1}/{retries})")
                response = self.session.get(full_url, stream=True, timeout=60)
                response.raise_for_status()
                with open(dest_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                logger.info(f"Successfully downloaded: {dest_path}")
                return True
            except Exception as e:
                logger.warning(f"Error downloading file {full_url}: {e}. Retrying...")
                if os.path.exists(dest_path):
                    try:
                        os.remove(dest_path)
                    except Exception:
                        pass
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                else:
                    logger.error(f"Failed to download file {full_url} after {retries} attempts.")
                    return False