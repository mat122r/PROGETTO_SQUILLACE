"""
transform/normalizza.py
=======================
Fase 2 – Normalizzazione

Legge i file grezzi:
  - data/fonte1_raw.csv   (ASMENET)
  - data/fonte2_raw.csv   (Halley)

Pulisce, allinea le colonne e salva:
  - data/tracciato_mezzo.csv

La funzione pubblica `normalizza()` può essere importata dagli orchestratori
della cartella skills/ per essere chiamata programmaticamente.
"""

import logging
import sys
from pathlib import Path
from typing import Optional, Union

import pandas as pd

# ---------------------------------------------------------------------------
# Configurazione logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Percorsi di default (relativi alla radice del progetto)
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

FILE_FONTE1 = DATA_DIR / "fonte1_raw.csv"
FILE_FONTE2 = DATA_DIR / "fonte2_raw.csv"
FILE_OUTPUT = DATA_DIR / "tracciato_mezzo.csv"

# Colonne del tracciato di mezzo (nell'ordine finale)
COLONNE_FINALI = [
    "id_fonte",
    "numero_pubblicazione",
    "tipo_atto",
    "numero_atto",
    "data_atto",
    "oggetto",
    "data_pubblicazione",
    "data_scadenza",
    "url_documento",
    "allegati",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _estrai_tipo_halley(testo: str) -> str:
    """
    Il campo `tipo` di Fonte2 ha la forma:
        "579\\n\\nMittente\\nCOMUNE DI SQUILLACE  \\n\\nTipo\\nDelibere di Giunta"
    Restituisce la parte dopo "Tipo\\n", oppure il testo originale se il
    pattern non è trovato.
    """
    if not isinstance(testo, str):
        return ""
    marker = "Tipo\n"
    idx = testo.find(marker)
    if idx == -1:
        return testo.strip()
    return testo[idx + len(marker):].strip()


# ---------------------------------------------------------------------------
# Elaborazione Fonte 1
# ---------------------------------------------------------------------------

def elabora_fonte1(path: Path) -> pd.DataFrame:
    log.info("=== FONTE 1 (ASMENET) ===")
    df = pd.read_csv(path, dtype=str, encoding="utf-8")
    log.info(f"  Righe lette:                    {len(df)}")

    # --- Pulizia 1: rimuovi righe con link_dettaglio vuoto ---
    prima = len(df)
    df = df[df["link_dettaglio"].notna() & (df["link_dettaglio"].str.strip() != "")]
    log.info(f"  Dopo rimozione link vuoti:      {len(df)}  (rimossi {prima - len(df)})")

    # --- Pulizia 2: rimuovi righe con numero_reg che inizia per "Pubblicazione" ---
    prima = len(df)
    df = df[~df["numero_reg"].str.strip().str.startswith("Pubblicazione", na=False)]
    log.info(f"  Dopo rimozione ann. pubblicaz.: {len(df)}  (rimossi {prima - len(df)})")

    # --- Mappatura colonne al tracciato di mezzo ---
    idx = df.index
    out = pd.DataFrame(index=idx)
    out["id_fonte"]             = pd.Series(1, index=idx)
    out["numero_pubblicazione"] = df["numero_reg"].str.strip()
    out["tipo_atto"]            = df["tipo"].str.strip()
    out["numero_atto"]          = pd.Series("", index=idx)
    out["data_atto"]            = df["data_pubblicazione_normalizzata"].str.strip()
    out["oggetto"]              = df["oggetto"].str.strip()
    out["data_pubblicazione"]   = df["data_pubblicazione_normalizzata"].str.strip()
    out["data_scadenza"]        = df["data_scadenza_normalizzata"].str.strip()
    out["url_documento"]        = df["link_dettaglio"].str.strip()
    out["allegati"]             = df["allegati"].fillna("").str.strip()

    log.info(f"  Righe Fonte1 nel tracciato:     {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Elaborazione Fonte 2
# ---------------------------------------------------------------------------

def elabora_fonte2(path: Path) -> pd.DataFrame:
    log.info("=== FONTE 2 (HALLEY) ===")
    df = pd.read_csv(path, dtype=str, encoding="utf-8")
    log.info(f"  Righe lette:                    {len(df)}")

    # --- Estrazione tipo effettivo ---
    df["tipo_atto"] = df["tipo"].apply(_estrai_tipo_halley)

    # Mostra i valori distinti estratti (per verifica)
    distinti = df["tipo_atto"].value_counts().to_dict()
    log.info(f"  Tipi distinti estratti:         {distinti}")

    # --- Mappatura colonne al tracciato di mezzo ---
    idx = df.index
    out = pd.DataFrame(index=idx)
    out["id_fonte"]             = pd.Series(2, index=idx)
    out["numero_pubblicazione"] = pd.Series("", index=idx)
    out["tipo_atto"]            = df["tipo_atto"].str.strip()
    out["numero_atto"]          = df["numero_atto"].str.strip()
    out["data_atto"]            = df["data_atto_normalizzata"].str.strip()
    out["oggetto"]              = df["oggetto"].str.strip()
    out["data_pubblicazione"]   = pd.Series("", index=idx)
    out["data_scadenza"]        = pd.Series("", index=idx)
    out["url_documento"]        = df["doc_principale_url"].fillna("").str.strip()
    out["allegati"]             = df["allegati"].fillna("").str.strip()

    log.info(f"  Righe Fonte2 nel tracciato:     {len(out)}")
    return out


# ---------------------------------------------------------------------------
# Funzione pubblica – importabile dagli orchestratori
# ---------------------------------------------------------------------------

def normalizza(
    csv_fonte1: Optional[Union[Path, str]] = None,
    csv_fonte2: Optional[Union[Path, str]] = None,
    output_csv: Optional[Union[Path, str]] = None,
) -> Path:
    """
    Esegue la normalizzazione e produce il tracciato di mezzo.

    Parametri
    ----------
    csv_fonte1 : percorso del CSV grezzo Fonte 1 (default: data/fonte1_raw.csv)
    csv_fonte2 : percorso del CSV grezzo Fonte 2 (default: data/fonte2_raw.csv)
    output_csv : percorso del CSV di output (default: data/tracciato_mezzo.csv)

    Restituisce
    -----------
    Path – percorso assoluto del file di output generato.
    """
    f1 = Path(csv_fonte1) if csv_fonte1 else FILE_FONTE1
    f2 = Path(csv_fonte2) if csv_fonte2 else FILE_FONTE2
    out = Path(output_csv) if output_csv else FILE_OUTPUT

    log.info("Avvio normalizzazione – Fase 2")
    log.info(f"  Fonte 1:  {f1}")
    log.info(f"  Fonte 2:  {f2}")
    log.info(f"  Output:   {out}")

    # Verifica esistenza file
    df_list = []
    
    if f1.exists():
        df_list.append(elabora_fonte1(f1))
    else:
        log.warning(f"File non trovato, salto Fonte 1: {f1}")

    if f2.exists():
        df_list.append(elabora_fonte2(f2))
    else:
        log.warning(f"File non trovato, salto Fonte 2: {f2}")
        
    if not df_list:
        log.error("Nessun file sorgente trovato per la normalizzazione.")
        raise FileNotFoundError("Nessun file sorgente trovato per la normalizzazione.")

    # --- Unione ---
    log.info("=== UNIONE ===")
    tracciato = pd.concat(df_list, ignore_index=True)

    # Assicura ordine colonne
    tracciato = tracciato[COLONNE_FINALI]

    log.info(f"  Totale righe nel tracciato:     {len(tracciato)}")
    log.info(f"  Distribuzione per fonte:\n{tracciato['id_fonte'].value_counts().to_string()}")

    # --- Salvataggio ---
    out.parent.mkdir(parents=True, exist_ok=True)
    tracciato.to_csv(out, index=False, encoding="utf-8", quoting=1)  # QUOTE_ALL
    log.info(f"  File salvato in: {out}")
    log.info("Normalizzazione completata con successo.")

    return out.resolve()


# ---------------------------------------------------------------------------
# Esecuzione diretta (comportamento invariato rispetto alla versione originale)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    normalizza()
