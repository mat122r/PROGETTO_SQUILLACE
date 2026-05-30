import os
import time
import logging
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class BaseScraper:
    def __init__(self, config):
        """
        Initializes the scraper with configuration options and sets up a requests session.
        """
        self.config = config
        self.base_url = config.get('base_url', '')
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })

    def fetch_page(self, url, params=None, retries=3, backoff=2):
        """
        Fetches a web page with retry capability and parses it into a BeautifulSoup object.
        """
        full_url = url if url.startswith('http') else urljoin(self.base_url, url)
        for attempt in range(retries):
            try:
                logger.info(f"Fetching: {full_url} with params {params} (Attempt {attempt+1}/{retries})")
                # ⚠️ Unica modifica: timeout aumentato da 30 a 120 secondi per pagine molto grandi
                response = self.session.get(full_url, params=params, timeout=120)
                response.raise_for_status()
                try:
                    return BeautifulSoup(response.content, 'lxml')
                except Exception:
                    return BeautifulSoup(response.content, 'html.parser')
            except Exception as e:
                logger.warning(f"Error fetching page {full_url}: {e}. Retrying in {backoff * (attempt + 1)}s...")
                if attempt < retries - 1:
                    time.sleep(backoff * (attempt + 1))
                else:
                    logger.error(f"Failed to fetch page {full_url} after {retries} attempts.")
                    raise e

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