"""
skills/run_static.py
====================
Orchestratore per portali statici (es. ASMENET).

Uso:
    python skills/run_static.py --config config/nuovo_portale.yaml

Il file YAML deve contenere almeno i campi:
    name, base_url, list_url, table_selector, row_selector, fields, ...

Vedere skills/template_static.yaml per un esempio completo commentato.
"""

import argparse
import logging
import sys
import time
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Percorso radice del progetto (due livelli sopra questo file)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

# Aggiungiamo la root al sys.path per importare i moduli del progetto
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers.fonte1_scraper import Fonte1Scraper
from transform.normalizza import normalizza
from load.carica_mysql import carica

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _carica_config(config_path: Path) -> dict:
    """Carica e valida il file di configurazione YAML."""
    if not config_path.exists():
        log.error(f"File di configurazione non trovato: {config_path}")
        sys.exit(1)
    try:
        with config_path.open(encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        log.error(f"Errore nel parsing del file YAML '{config_path}': {exc}")
        sys.exit(1)

    if not isinstance(cfg, dict):
        log.error("Il file YAML deve contenere un dizionario di configurazione.")
        sys.exit(1)

    campi_obbligatori = ["name", "base_url", "list_url", "table_selector", "row_selector", "fields"]
    mancanti = [c for c in campi_obbligatori if c not in cfg]
    if mancanti:
        log.error(f"Campi obbligatori mancanti nel file YAML: {mancanti}")
        sys.exit(1)

    return cfg


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestratore ETL per portali statici (BeautifulSoup).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python skills/run_static.py --config config/sources.yaml
  python skills/run_static.py --config config/nuovo_portale.yaml --no-load
        """
    )
    parser.add_argument(
        "--config",
        required=True,
        metavar="PERCORSO_YAML",
        help="Percorso del file YAML di configurazione del portale.",
    )
    parser.add_argument(
        "--output-csv",
        default=None,
        metavar="PERCORSO_CSV",
        help="Percorso del CSV grezzo di output (default: data/fonte1_raw.csv).",
    )
    parser.add_argument(
        "--tracciato",
        default=None,
        metavar="PERCORSO_CSV",
        help="Percorso del tracciato di mezzo (default: data/tracciato_mezzo.csv).",
    )
    parser.add_argument(
        "--no-normalize",
        action="store_true",
        help="Salta la fase di normalizzazione.",
    )
    parser.add_argument(
        "--no-load",
        action="store_true",
        help="Salta la fase di caricamento su MySQL.",
    )
    parser.add_argument(
        "--db-host", default=None, help="Host MySQL (sovrascrive il default)."
    )
    parser.add_argument(
        "--db-user", default=None, help="Utente MySQL (sovrascrive il default)."
    )
    parser.add_argument(
        "--db-password", default=None, help="Password MySQL (sovrascrive il default)."
    )
    parser.add_argument(
        "--db-name", default=None, help="Nome database MySQL (sovrascrive il default)."
    )
    args = parser.parse_args()

    t_start = time.time()
    config_path = Path(args.config).resolve()

    log.info("=" * 60)
    log.info("  SKILL: run_static – Pipeline ETL per portali statici")
    log.info("=" * 60)
    log.info(f"  Config:  {config_path}")

    # ------------------------------------------------------------------
    # 1. Caricamento configurazione
    # ------------------------------------------------------------------
    cfg = _carica_config(config_path)
    log.info(f"  Portale: {cfg.get('name', 'N/D')}")
    log.info(f"  URL:     {cfg.get('base_url', 'N/D')}")

    # ------------------------------------------------------------------
    # 2. Estrazione – Fonte1Scraper (scraping statico con BeautifulSoup)
    # ------------------------------------------------------------------
    log.info("")
    log.info("─" * 60)
    log.info("  FASE 1 – Estrazione (scraping statico)")
    log.info("─" * 60)

    try:
        scraper = Fonte1Scraper(cfg)
        csv_grezzo = scraper.run()
        log.info(f"  CSV grezzo prodotto: {csv_grezzo}")
    except Exception as exc:
        log.error(f"Errore durante l'estrazione: {exc}")
        sys.exit(1)

    # Sovrascrittura percorso CSV grezzo se specificato
    if args.output_csv:
        csv_grezzo = args.output_csv

    # ------------------------------------------------------------------
    # 3. Normalizzazione
    # ------------------------------------------------------------------
    if args.no_normalize:
        log.info("")
        log.info("  FASE 2 – Normalizzazione SALTATA (--no-normalize)")
        tracciato_path = args.tracciato
    else:
        log.info("")
        log.info("─" * 60)
        log.info("  FASE 2 – Normalizzazione")
        log.info("─" * 60)
        try:
            # La normalizzazione usa fonte1_raw come input; fonte2 viene
            # letta dal percorso di default se non specificata.
            tracciato_path = normalizza(
                csv_fonte1=csv_grezzo,
                output_csv=args.tracciato or None,
            )
            log.info(f"  Tracciato di mezzo: {tracciato_path}")
        except FileNotFoundError as exc:
            log.error(f"Errore normalizzazione – file mancante: {exc}")
            sys.exit(1)
        except Exception as exc:
            log.error(f"Errore durante la normalizzazione: {exc}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # 4. Caricamento su MySQL
    # ------------------------------------------------------------------
    risultato = None
    if args.no_load:
        log.info("")
        log.info("  FASE 3 – Caricamento MySQL SALTATO (--no-load)")
    else:
        log.info("")
        log.info("─" * 60)
        log.info("  FASE 3 – Caricamento su MySQL")
        log.info("─" * 60)
        try:
            risultato = carica(
                tracciato_csv=tracciato_path,
                host=args.db_host,
                user=args.db_user,
                password=args.db_password,
                database=args.db_name,
            )
        except FileNotFoundError as exc:
            log.error(f"Errore caricamento – file mancante: {exc}")
            sys.exit(1)
        except Exception as exc:
            log.error(f"Errore durante il caricamento MySQL: {exc}")
            sys.exit(1)

    # ------------------------------------------------------------------
    # 5. Riepilogo finale
    # ------------------------------------------------------------------
    t_elapsed = time.time() - t_start
    log.info("")
    log.info("=" * 60)
    log.info("  RIEPILOGO FINALE")
    log.info("=" * 60)
    log.info(f"  Portale elaborato:   {cfg.get('name', 'N/D')}")
    log.info(f"  CSV grezzo:          {csv_grezzo}")
    if tracciato_path:
        log.info(f"  Tracciato di mezzo:  {tracciato_path}")
    if risultato:
        log.info(f"  Atti inseriti:       {risultato['tot_atti']}")
        log.info(f"  Documenti inseriti:  {risultato['tot_docs']}")
    log.info(f"  Tempo totale:        {t_elapsed:.1f}s")
    log.info("  Pipeline completata con successo. ✓")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
