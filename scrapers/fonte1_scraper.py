import os
import re
import logging
import pandas as pd
from datetime import datetime
from urllib.parse import urljoin
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

class Fonte1Scraper(BaseScraper):
    def __init__(self, config):
        super().__init__(config)

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
        logger.warning(f"Could not parse date string: {date_str}")
        return date_str

    def sanitize_filename(self, filename):
        """
        Sanitizes a filename by removing invalid characters.
        """
        if not filename:
            return "unnamed_file"
        
        # Decodifica esplicita mojibake se presente 
        # (se era codificato male come Â, es. \xc2\xa0 letto come latin1)
        try:
            filename = filename.encode('latin1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
            
        # Sostituisci NBSP con spazio normale
        filename = filename.replace('\xa0', ' ').replace('\u00A0', ' ')
        
        # Rimuovi spazi anomali o caratteri di controllo
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        filename = re.sub(r'\s+', ' ', filename).strip()
        
        # Remove any characters not allowed in Windows file names
        filename = re.sub(r'[\\/*?:"<>|]', '_', filename)
        
        return filename

    def run(self):
        logger.info("Avvio scraper per Fonte 1: ASMENET Squillace")
        
        # Carica la pagina principale con la lista degli atti
        list_url = urljoin(self.base_url, self.config['list_url'])
        soup = self.fetch_page(list_url)

        # Gestione esplicita del caso in cui il server non risponde
        if soup is None:
            raise ConnectionError(
                "Il server del comune è temporaneamente lento o non risponde. "
                "Salto la fonte corrente."
            )
        
        # Find the table containing the acts
        table_selector = self.config['table_selector']
        table = soup.select_one(table_selector)
        if not table:
            logger.error(f"Tabella non trovata con selettore: {table_selector}")
            raise Exception("Tabella principale non trovata.")

        row_selector = self.config['row_selector']
        rows = table.select(row_selector)
        total_rows = len(rows)
        logger.info(f"Found {total_rows} rows in the list table.")

        records = []
        skip_next = False
        annullato_style = self.config.get('annullato', {}).get('style_contains', 'text-decoration: line-through')
        skip_next_row_config = self.config.get('annullato', {}).get('skip_next_row', True)

        for idx, row in enumerate(rows):
            # Check if this row is to be skipped as the successor to an annullato row
            if skip_next:
                logger.info(f"Row {idx + 1}/{total_rows} skipped as it is the successor to a cancelled act.")
                skip_next = False
                continue

            # Check if the current row itself contains the cancelled style
            style_str = str(row.get('style', ''))
            if annullato_style in style_str:
                logger.info(f"Row {idx + 1}/{total_rows} is cancelled (has line-through style). Skipping.")
                if skip_next_row_config:
                    skip_next = True
                continue

            # Extract fields defined in configuration
            fields = self.config['fields']
            record = {}
            for field_name, sel in fields.items():
                element = row.select_one(sel)
                if element:
                    if field_name == 'link_dettaglio':
                        record[field_name] = element.get('href', '')
                    else:
                        record[field_name] = element.get_text(strip=True)
                else:
                    record[field_name] = ""

            numero_reg = record.get('numero_reg', '')
            if not numero_reg:
                logger.warning(f"Row {idx + 1}/{total_rows} has no registration number. Skipping.")
                continue

            logger.info(f"Processing row {idx + 1}/{total_rows} - Reg N.: {numero_reg}")

            # Normalise dates
            record['data_pubblicazione_normalizzata'] = self.normalize_date(record.get('data_pubblicazione', ''))
            record['data_scadenza_normalizzata'] = self.normalize_date(record.get('data_scadenza', ''))

            # Controllo early exit per la modalità incrementale
            # La chiave è solo numero_reg, in linea con _build_key di run_static.py
            if hasattr(self, 'keys_to_skip') and self.keys_to_skip:
                current_key = str(numero_reg).strip()
                if current_key in self.keys_to_skip:
                    logger.info("Raggiunto record già processato. Interruzione incrementale.")
                    break

            # Visita la pagina di dettaglio per recuperare gli allegati
            detail_rel_url = record.get('link_dettaglio', '')
            downloaded_paths = []

            if detail_rel_url:
                detail_url = urljoin(self.base_url, detail_rel_url)
                # Salva link_dettaglio come URL assoluto
                record['link_dettaglio'] = detail_url
                try:
                    detail_soup = self.fetch_page(detail_url)
                    if detail_soup is None:
                        logger.warning(f"Pagina dettaglio non raggiungibile per reg. {numero_reg}. Allegati saltati.")
                        record['allegati'] = ""
                        records.append(record)
                        continue
                    dettaglio_table_selector = self.config['dettaglio_table_selector']
                    dettaglio_table = detail_soup.select_one(dettaglio_table_selector)
                    
                    if dettaglio_table:
                        dettaglio_rows = dettaglio_table.select(self.config['dettaglio_allegato_row'])
                        for d_row in dettaglio_rows:
                            name_el = d_row.select_one(self.config['dettaglio_nome_file'])
                            link_el = d_row.select_one(self.config['dettaglio_link_download'])
                            
                            if name_el and link_el:
                                raw_filename = name_el.get_text(strip=True)
                                download_href = link_el.get('href', '')
                                
                                if download_href:
                                    sanitized_name = self.sanitize_filename(raw_filename)
                                    # Handle case where file extension is missing or needs preserving
                                    # Ensure download folder matches details
                                    dest_folder = os.path.join("allegati", "fonte1", numero_reg)
                                    dest_path = os.path.join(dest_folder, sanitized_name)
                                    
                                    # Build final download URL
                                    download_url = urljoin(self.base_url, download_href)
                                    
                                    # Perform download
                                    # We pass the absolute path for file creation
                                    abs_dest_path = os.path.abspath(dest_path)
                                    success = self.download_file(download_url, abs_dest_path)
                                    if success:
                                        # Store the relative path using forward slashes for cross-platform compatibility
                                        rel_path = f"allegati/fonte1/{numero_reg}/{sanitized_name}"
                                        downloaded_paths.append(rel_path)
                    else:
                        logger.info(f"No attachment table found for registration number {numero_reg}.")
                except Exception as e:
                    logger.error(f"Error scraping details page for registration number {numero_reg}: {e}")
            else:
                logger.warning(f"No detail link found for registration number {numero_reg}")

            # Store the comma-separated attachments relative paths
            record['allegati'] = ",".join(downloaded_paths)
            records.append(record)

        # Create output CSV
        os.makedirs("data", exist_ok=True)
        csv_path = os.path.join("data", "fonte1_raw.csv")
        df = pd.DataFrame(records)
        
        # Ensure correct column ordering
        cols = [
            'numero_reg', 'tipo', 'ente', 'oggetto', 'data_pubblicazione', 
            'data_scadenza', 'link_dettaglio', 'allegati', 
            'data_pubblicazione_normalizzata', 'data_scadenza_normalizzata'
        ]
        # Only keep columns that are present, just in case
        cols = [c for c in cols if c in df.columns]
        df = df[cols]
        
        df.to_csv(csv_path, index=False, encoding='utf-8')
        logger.info(f"Successfully finished Fonte 1 scraper. Saved data to {csv_path}")
        return csv_path
