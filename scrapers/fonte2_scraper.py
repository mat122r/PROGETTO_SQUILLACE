import os
import re
import time
import logging
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin, urlparse, parse_qs
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class Fonte2Scraper(BaseScraper):
    def __init__(self, config):
        super().__init__(config)
        self.driver = None

    def init_driver(self):
        """
        Initializes Chrome driver in headless mode.
        """
        logger.info("Initializing Headless Chrome driver...")
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Suppress logging
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.info("Chrome driver initialized successfully.")

    def close_driver(self):
        if self.driver:
            logger.info("Closing Chrome driver...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
            self.driver = None

    def extract_mc_param(self, onclick_str):
        """
        Extracts the value of the 'mc' parameter from an onclick attribute.
        e.g., location.href='mc_attachment.php?mc=12345' -> 12345
        """
        if not onclick_str:
            return None
        # Try to find mc=something in the onclick string
        match = re.search(r'mc=([^&\'"\)]+)', onclick_str)
        if match:
            return match.group(1).strip()
        return None

    def normalize_date(self, date_str):
        """
        Converts date from gg/mm/aaaa to YYYY-MM-DD format.
        """
        if not date_str:
            return ""
        date_str = date_str.strip()
        for fmt in ('%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d'):
            try:
                return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
            except ValueError:
                continue
        return date_str

    def clean_filename(self, text):
        """
        Cleans filename by removing prefix 'Documento - ' and invalid characters.
        """
        if not text:
            return "unnamed_file"
        # Remove prefix "Documento - " (case insensitive)
        text = re.sub(r'^Documento\s*-\s*', '', text, flags=re.IGNORECASE)
        text = text.strip()
        # Remove invalid chars for filenames
        text = re.sub(r'[\\/*?:"<>|]', '_', text)
        return text

    def run(self):
        logger.info("Starting scraper for Fonte 2: Halley Squillace")
        
        # Initialize Selenium driver
        self.init_driver()
        
        records = []
        page_num = self.config.get('pagination_start', 0)
        list_url_base = urljoin(self.base_url, self.config['list_url'])
        
        limit_date = datetime.strptime("12/04/2024", "%d/%m/%Y")
        
        try:
            while True:
                # Build target page URL
                target_url = f"{list_url_base}&{self.config.get('pagination_param', 'pag')}={page_num}"
                logger.info(f"Navigating to page {page_num}: {target_url}")
                
                self.driver.get(target_url)
                
                # Wait for the table-albo to load
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.ID, "table-albo"))
                    )
                    # Let javascript settle slightly
                    time.sleep(1)
                except Exception as e:
                    logger.warning(f"Timeout waiting for table-albo on page {page_num}. Ending pagination loop.")
                    break
                
                # Pass page source to BeautifulSoup for fast parsing
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Find all rows in the tbody
                row_selector = self.config['row_selector']
                rows = soup.select(row_selector)
                
                if not rows:
                    logger.info(f"No rows found on page {page_num}. Ending pagination.")
                    break
                
                logger.info(f"Found {len(rows)} rows on page {page_num}. Extracting...")
                
                valid_on_this_page = 0
                older_than_limit_on_this_page = 0
                
                for idx, row in enumerate(rows):
                    tds = row.find_all('td', recursive=False)
                    if len(tds) < 6:
                        # Row does not contain enough cells
                        continue
                    
                    # 1. Tipo (First cell)
                    # Get cell, remove <strong>Tipo</strong> text to isolate value
                    td1 = tds[0]
                    strong_tipo = td1.find('strong')
                    if strong_tipo:
                        strong_text = strong_tipo.get_text()
                        tipo = td1.get_text().replace(strong_text, '').strip()
                    else:
                        tipo = td1.get_text(strip=True)
                    tipo = tipo.lstrip(':').strip()
                    
                    # Filter: tipo must contain 'Delibere' (case insensitive)
                    filter_tipo = self.config.get('filter_tipo', 'Delibere')
                    if filter_tipo.lower() not in tipo.lower():
                        # Skip this record as it is not a Delibera
                        continue
                        
                    # 2. Oggetto & Detail Link (Second cell)
                    td2 = tds[1]
                    a_link = td2.find('a')
                    if not a_link:
                        continue
                    oggetto = a_link.get_text(strip=True)
                    link_dettaglio_href = a_link.get('href', '')
                    
                    # 3. Numero atto & Data atto (Third cell)
                    td3 = tds[2]
                    td3_text = td3.get_text()
                    num_match = re.search(r'Numero\s+atto\s*:?\s*(.*?)(?=\s*Data\s+atto|$)', td3_text, re.IGNORECASE)
                    data_match = re.search(r'Data\s+atto\s*:?\s*(\d{2}/\d{2}/\d{4})', td3_text, re.IGNORECASE)
                    
                    numero_atto = num_match.group(1).strip() if num_match else ""
                    data_atto = data_match.group(1).strip() if data_match else ""
                    
                    if not numero_atto or not data_atto:
                        logger.warning(f"Missing Numero Atto ({numero_atto}) or Data Atto ({data_atto}) on page {page_num}, row {idx+1}. Skipping.")
                        continue
                        
                    # Check Date filter >= 12/04/2024
                    try:
                        date_obj = datetime.strptime(data_atto, "%d/%m/%Y")
                    except Exception as date_err:
                        logger.error(f"Error parsing date {data_atto}: {date_err}")
                        continue
                        
                    if date_obj < limit_date:
                        older_than_limit_on_this_page += 1
                        continue
                        
                    valid_on_this_page += 1
                    
                    # 4. Documento Principale (Sixth cell)
                    td6 = tds[5]
                    a_doc = td6.select_one(self.config['fields']['documento_principale'].split("td:nth-child(6) ")[-1])
                    doc_principale_url = ""
                    if a_doc:
                        onclick_str = a_doc.get('onclick', '')
                        mc_val = self.extract_mc_param(onclick_str)
                        if mc_val:
                            doc_principale_url = f"https://portale5.halleysud.it/squillace/mc/mc_attachment.php?mc={mc_val}"
                    
                    # Compose detail URL
                    detail_url = urljoin(self.base_url, link_dettaglio_href)
                    
                    record = {
                        'tipo': tipo,
                        'oggetto': oggetto,
                        'numero_atto': numero_atto,
                        'data_atto': data_atto,
                        'doc_principale_url': doc_principale_url,
                        'link_dettaglio': detail_url,
                        'data_atto_normalizzata': self.normalize_date(data_atto)
                    }
                    
                    # Process downloads:
                    dest_folder = os.path.join("allegati", "fonte2", numero_atto)
                    downloaded_paths = []
                    
                    # Download Main Document
                    if doc_principale_url:
                        # Construct a file name for the main document
                        main_doc_filename = f"Delibera_n_{numero_atto}_Documento_Principale.pdf"
                        dest_path_main = os.path.join(dest_folder, main_doc_filename)
                        
                        logger.info(f"Downloading main doc for Act {numero_atto}...")
                        abs_dest_path_main = os.path.abspath(dest_path_main)
                        success = self.download_file(doc_principale_url, abs_dest_path_main)
                        if success:
                            downloaded_paths.append(f"allegati/fonte2/{numero_atto}/{main_doc_filename}")
                    
                    # Visit detail page for additional attachments
                    try:
                        logger.info(f"Visiting details page for Act {numero_atto}: {detail_url}")
                        detail_soup = self.fetch_page(detail_url)
                        
                        # Find all attachment links
                        dettaglio_allegato_selector = self.config['dettaglio_allegato_selector']
                        attachment_links = detail_soup.select(dettaglio_allegato_selector)
                        
                        for a_att in attachment_links:
                            att_onclick = a_att.get('onclick', '')
                            att_mc = self.extract_mc_param(att_onclick)
                            
                            if att_mc:
                                att_url = f"https://portale5.halleysud.it/squillace/mc/mc_attachment.php?mc={att_mc}"
                                # Extract filename from link text
                                raw_att_name = a_att.get_text(strip=True)
                                cleaned_att_name = self.clean_filename(raw_att_name)
                                
                                # Make sure it has a valid extension (default to .pdf if not present)
                                if not os.path.splitext(cleaned_att_name)[1]:
                                    cleaned_att_name += ".pdf"
                                    
                                # Prevent matching the main doc filename if named the same
                                if cleaned_att_name == f"Delibera_n_{numero_atto}_Documento_Principale.pdf":
                                    cleaned_att_name = "Allegato_" + cleaned_att_name
                                    
                                dest_path_att = os.path.join(dest_folder, cleaned_att_name)
                                abs_dest_path_att = os.path.abspath(dest_path_att)
                                
                                logger.info(f"Downloading attachment: {cleaned_att_name}...")
                                success_att = self.download_file(att_url, abs_dest_path_att)
                                if success_att:
                                    downloaded_paths.append(f"allegati/fonte2/{numero_atto}/{cleaned_att_name}")
                    except Exception as detail_err:
                        logger.error(f"Error scraping details page for Act {numero_atto}: {detail_err}")
                        
                    # Save relative paths separated by comma
                    record['allegati'] = ",".join(downloaded_paths)
                    records.append(record)
                    
                    logger.info(f"Processed Act {numero_atto} with {len(downloaded_paths)} downloaded file(s).")
                
                logger.info(f"Page {page_num} finished. Valid records: {valid_on_this_page}, Older than limit: {older_than_limit_on_this_page}")
                
                # If all records on this page were older than limit, we can terminate pagination safely
                # (since acts are in descending order).
                if len(rows) > 0 and older_than_limit_on_this_page == len(rows):
                    logger.info("All records on this page are older than 12/04/2024. Ending pagination loop.")
                    break
                    
                # Increment page number
                page_num += 1
                
        finally:
            self.close_driver()
            
        # Save to CSV
        os.makedirs("data", exist_ok=True)
        csv_path = os.path.join("data", "fonte2_raw.csv")
        df = pd.DataFrame(records)
        
        # Ensure column ordering matching requirements
        cols = [
            'tipo', 'oggetto', 'numero_atto', 'data_atto', 
            'doc_principale_url', 'allegati', 'data_atto_normalizzata'
        ]
        cols = [c for c in cols if c in df.columns]
        if cols:
            df = df[cols]
            
        df.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"Successfully finished Fonte 2 scraper. Saved data to {csv_path}")
        return csv_path
