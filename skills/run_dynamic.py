"""
skills/run_dynamic.py
=====================
Orchestratore per portali dinamici (es. Halley – richiede Selenium).

Uso:
    python skills/run_dynamic.py --config config/portale.yaml
    python skills/run_dynamic.py --config config/portale.yaml --incremental

Vedere skills/SKILL.md per il workflow completo e skills/template_dynamic.yaml
per un esempio di configurazione commentato.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional, Set

import pandas as pd
import yaml

# Fix encoding per terminali Windows (cp1252 non supporta caratteri Unicode)
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# ---------------------------------------------------------------------------
# Percorso radice del progetto (due livelli sopra questo file)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scrapers.fonte2_scraper import Fonte2Scraper
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
# Costanti per la modalità incrementale
# ---------------------------------------------------------------------------
STATE_FILE = ROOT / "data" / ".last_run_dynamic.json"


# ---------------------------------------------------------------------------
# Helpers – configurazione
# ---------------------------------------------------------------------------

def _carica_config(config_path: Path) -> dict:
    """Carica e valida il file YAML di configurazione."""
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

    campi_obbligatori = [
        "name", "base_url", "list_url", "row_selector", "fields",
        "pagination_param", "filter_tipo",
    ]
    mancanti = [c for c in campi_obbligatori if c not in cfg]
    if mancanti:
        log.error(f"Campi obbligatori mancanti nel file YAML: {mancanti}")
        sys.exit(1)

    return cfg


# ---------------------------------------------------------------------------
# Helpers – modalità incrementale
# ---------------------------------------------------------------------------

def _build_key(row: pd.Series) -> str:
    """Costruisce la chiave univoca per un record del CSV grezzo dinamico."""
    numero_atto = str(row.get("numero_atto", "")).strip()
    data = str(row.get("data_atto_normalizzata") or row.get("data_atto", "")).strip()
    return f"{numero_atto}||{data}"


def _carica_stato() -> Set[str]:
    """Carica il file di stato incrementale. Restituisce un set di chiavi già processate."""
    if not STATE_FILE.exists():
        return set()
    try:
        with STATE_FILE.open(encoding="utf-8") as f:
            data = json.load(f)
        keys = set(data.get("processed_keys", []))
        log.info(f"  Stato incrementale caricato: {len(keys)} chiavi già processate.")
        return keys
    except (json.JSONDecodeError, KeyError) as exc:
        log.warning(f"File di stato corrotto, verrà ricreato: {exc}")
        return set()


def _salva_stato(keys: Set[str]) -> None:
    """Salva il file di stato aggiornato con tutte le chiavi processate."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "processed_keys": sorted(keys),
    }
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(f"  Stato incrementale aggiornato: {len(keys)} chiavi totali → {STATE_FILE}")


def _filtra_incrementale(csv_path: str, chiavi_processate: Set[str]):
    """
    Legge il CSV grezzo, filtra i record già processati e salva un CSV temporaneo
    con i soli nuovi record. Restituisce (Path del CSV filtrato, set di nuove chiavi),
    oppure (None, set()) se non ci sono nuovi record.
    """
    try:
        df = pd.read_csv(csv_path, dtype=str, encoding="utf-8")
    except (pd.errors.EmptyDataError, FileNotFoundError):
        df = pd.DataFrame()

    if df.empty:
        log.info("  Nessun record presente nel CSV grezzo.")
        return None, set()

    df["_key"] = df.apply(_build_key, axis=1)

    df_nuovi = df[~df["_key"].isin(chiavi_processate)].copy()
    nuove_chiavi = set(df_nuovi["_key"].tolist())

    log.info(f"  Record totali nel CSV grezzo:  {len(df)}")
    log.info(f"  Record già processati:         {len(df) - len(df_nuovi)}")
    log.info(f"  Nuovi record da elaborare:     {len(df_nuovi)}")

    if df_nuovi.empty:
        return None, set()

    df_nuovi = df_nuovi.drop(columns=["_key"])
    csv_filtrato = Path(csv_path).parent / ".filtered_dynamic.csv"
    df_nuovi.to_csv(csv_filtrato, index=False, encoding="utf-8")
    return csv_filtrato, nuove_chiavi


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Orchestratore ETL per portali dinamici (Selenium).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Pipeline completa
  python skills/run_dynamic.py --config config/sources.yaml

  # Solo nuovi atti (modalità incrementale)
  python skills/run_dynamic.py --config config/sources.yaml --incremental

  # Solo estrazione, senza normalizzazione né caricamento
  python skills/run_dynamic.py --config config/sources.yaml --no-normalize --no-load
        """
    )
    parser.add_argument(
        "--config", required=True, metavar="PERCORSO_YAML",
        help="Percorso del file YAML di configurazione del portale.",
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Elabora solo i record non ancora processati (basato su .last_run_dynamic.json).",
    )
    parser.add_argument(
        "--output-csv", default=None, metavar="PERCORSO_CSV",
        help="Percorso del CSV grezzo di output (default: data/fonte2_raw.csv).",
    )
    parser.add_argument(
        "--tracciato", default=None, metavar="PERCORSO_CSV",
        help="Percorso del tracciato di mezzo (default: data/tracciato_mezzo.csv).",
    )
    parser.add_argument("--no-normalize", action="store_true", help="Salta la normalizzazione.")
    parser.add_argument("--no-load", action="store_true", help="Salta il caricamento su MySQL.")
    parser.add_argument("--db-host", default=None, help="Host MySQL.")
    parser.add_argument("--db-user", default=None, help="Utente MySQL.")
    parser.add_argument("--db-password", default=None, help="Password MySQL.")
    parser.add_argument("--db-name", default=None, help="Nome database MySQL.")
    args = parser.parse_args()

    t_start = time.time()
    config_path = Path(args.config).resolve()

    log.info("=" * 60)
    log.info("  SKILL: run_dynamic – Pipeline ETL per portali dinamici")
    if args.incremental:
        log.info("  Modalità: INCREMENTALE (solo nuovi atti)")
    else:
        log.info("  Modalità: COMPLETA")
    log.info("=" * 60)
    log.info(f"  Config: {config_path}")

    # ------------------------------------------------------------------
    # 1. Configurazione
    # ------------------------------------------------------------------
    cfg = _carica_config(config_path)
    log.info(f"  Portale: {cfg.get('name', 'N/D')}")
    log.info(f"  URL:     {cfg.get('base_url', 'N/D')}")

    # ------------------------------------------------------------------
    # 2. Estrazione (Selenium)
    # ------------------------------------------------------------------
    log.info("")
    log.info("─" * 60)
    log.info("  FASE 1 – Estrazione (scraping dinamico con Selenium)")
    log.info("─" * 60)
    log.info("  Avvio Chrome headless – questa fase può richiedere diversi minuti.")

    chiavi_processate: Set[str] = set()
    if args.incremental:
        chiavi_processate = _carica_stato()

    try:
        scraper = Fonte2Scraper(cfg)
        if args.incremental:
            scraper.keys_to_skip = chiavi_processate
        csv_grezzo = scraper.run()
        log.info(f"  CSV grezzo prodotto: {csv_grezzo}")
    except ConnectionError as exc:
        # Errore di rete: il server non risponde. Messaggio chiaro e uscita pulita.
        print(f"\n[AVVISO RETE] {exc}")
        log.warning("Estrazione Fonte 2 saltata per errore di rete. Il processo può proseguire con le altre fonti.")
        sys.exit(0)   # exit(0) = nessun errore fatale, il master pipeline può continuare
    except Exception as exc:
        log.error(f"Errore durante l'estrazione: {exc}")
        sys.exit(1)

    if args.output_csv:
        csv_grezzo = args.output_csv

    # ------------------------------------------------------------------
    # 3. Filtro incrementale (se richiesto)
    # ------------------------------------------------------------------
    nuove_chiavi: Set[str] = set()
    csv_da_normalizzare = csv_grezzo

    if args.incremental:
        log.info("")
        log.info("─" * 60)
        log.info("  FILTRO INCREMENTALE")
        log.info("─" * 60)
        csv_filtrato, nuove_chiavi = _filtra_incrementale(csv_grezzo, chiavi_processate)

        if csv_filtrato is None:
            t_elapsed = time.time() - t_start
            log.info("")
            log.info("=" * 60)
            log.info("  Nessun nuovo atto da processare. Database già aggiornato.")
            log.info(f"  Tempo totale: {t_elapsed:.1f}s")
            log.info("=" * 60)
            return

        csv_da_normalizzare = str(csv_filtrato)
    else:
        try:
            df_full = pd.read_csv(csv_grezzo, dtype=str, encoding="utf-8")
            df_full["_key"] = df_full.apply(_build_key, axis=1)
            nuove_chiavi = set(df_full["_key"].tolist())
        except Exception:
            nuove_chiavi = set()

    # ------------------------------------------------------------------
    # 4. Normalizzazione
    # ------------------------------------------------------------------
    tracciato_path = None
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
            tracciato_path = normalizza(
                csv_fonte2=csv_da_normalizzare,
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
    # 5. Caricamento su MySQL
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
    # 6. Aggiornamento stato incrementale
    # ------------------------------------------------------------------
    if nuove_chiavi:
        chiavi_aggiornate = chiavi_processate | nuove_chiavi
        _salva_stato(chiavi_aggiornate)

    # ------------------------------------------------------------------
    # 7. Riepilogo finale
    # ------------------------------------------------------------------
    t_elapsed = time.time() - t_start
    log.info("")
    log.info("=" * 60)
    log.info("  RIEPILOGO FINALE")
    log.info("=" * 60)
    log.info(f"  Portale elaborato:   {cfg.get('name', 'N/D')}")
    log.info(f"  Modalità:            {'Incrementale' if args.incremental else 'Completa'}")
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
