"""
load/carica_mysql.py
====================
Fase 3 - Caricamento MySQL nel database intermediMC

Legge:  data/tracciato_mezzo.csv
Popola: mcputerecupubbinte  (atti)
        mcrecorecuallepubb  (documenti e allegati)

Il database si connette con il nome fisico "intermedimc.sql"
(MySQL su Windows ha importato lo schema con il nome del file incluso).

La funzione pubblica `carica()` può essere importata dagli orchestratori
della cartella skills/ per essere chiamata programmaticamente.
"""

import logging
import re
import sys
from pathlib import Path
from typing import Optional, Union

import mysql.connector
import pandas as pd

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
# Percorsi di default
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
FILE_CSV = BASE_DIR / "data" / "tracciato_mezzo.csv"

# ---------------------------------------------------------------------------
# Connessione DB di default
# Il database e' stato creato importando intermediMC.sql in HeidiSQL.
# Il nome del database risultante e' "intermedimc" (MySQL case-insensitive).
# ---------------------------------------------------------------------------
DB_CONFIG = dict(
    host="localhost",
    port=3306,
    user="root",
    password="admin",
    database="intermedimc",        # nome del database in MySQL
    charset="latin1",
    collation="latin1_swedish_ci",
    use_unicode=False,             # invia byte latin1 nativi
)

COMMIT_OGNI = 100

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_ZERO = "0001-01-01"


def _valida_data(val) -> str:
    """Restituisce la data YYYY-MM-DD se valida, altrimenti DATE_ZERO."""
    if val is None:
        return DATE_ZERO
    s = str(val).strip()
    if s in ("", "nan", "NaN", "None"):
        return DATE_ZERO
    return s if DATE_RE.match(s) else DATE_ZERO


def _str(val, maxlen: int = 0, default: str = "") -> str:
    """Converte valore pandas in stringa pulita; tronca se maxlen > 0."""
    if val is None:
        return default
    if isinstance(val, float):
        return default      # NaN -> default
    s = str(val).strip()
    if s in ("", "nan", "NaN", "None"):
        return default
    return s[:maxlen] if maxlen else s


def _anno(data_pub: str, data_atto: str) -> int:
    """Estrae l'anno da data_pubblicazione, poi da data_atto, altrimenti 0."""
    for d in (data_pub, data_atto):
        if d and d != DATE_ZERO:
            return int(d[:4])
    return 0


def _nome_da_url(url: str) -> str:
    """Estrae il nome file dall'URL (parte dopo l'ultimo '/')."""
    url = url.strip()
    parte = url.rsplit("/", 1)[-1]
    return (parte if parte else url)[:250]


def _nome_da_percorso(perc: str) -> str:
    """Estrae il nome file dal percorso (supporta / e \\)."""
    perc = perc.strip()
    for sep in ("/", "\\"):
        if sep in perc:
            perc = perc.rsplit(sep, 1)[-1]
    return perc[:250]


def _enc(s: str) -> bytes:
    """Codifica in latin1, sostituendo i caratteri non rappresentabili."""
    return s.encode("latin1", errors="replace")


# ---------------------------------------------------------------------------
# SQL
# ---------------------------------------------------------------------------

SQL_ATTO = """
INSERT INTO `mcputerecupubbinte`
    (MCRECU_OGG_NTC, MCRECU_ATT_DAT, MCRECU_TPATT_DES,
     MCRECU_NUM_PR6_COA, MCRECU_PBU_DAT, MCRECU_SCD_DAT,
     MCRECU_PBU_NUM, MCRECU_PBU_ANN)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
"""

SQL_DOC = """
INSERT INTO `mcrecorecuallepubb`
    (MCRECA_PBU_NUM, MCRECA_PBU_ANN, MCRECA_DOCPR_FLG,
     MCRECA_DESC_DSL, MCRECA_PERCAL_DES)
VALUES (%s, %s, %s, %s, %s)
"""


# ---------------------------------------------------------------------------
# Funzione pubblica – importabile dagli orchestratori
# ---------------------------------------------------------------------------

def carica(
    tracciato_csv: Optional[Union[Path, str]] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    database: Optional[str] = None,
) -> dict:
    """
    Carica il tracciato di mezzo su MySQL.

    Parametri
    ----------
    tracciato_csv : percorso del CSV tracciato di mezzo
                    (default: data/tracciato_mezzo.csv)
    host          : host MySQL (default: "localhost")
    user          : utente MySQL (default: "root")
    password      : password MySQL (default: "")
    database      : nome database MySQL (default: "intermedimc")

    Restituisce
    -----------
    dict con le chiavi:
        "tot_atti"  – numero di atti inseriti
        "tot_docs"  – numero di documenti/allegati inseriti
    """
    file_csv = Path(tracciato_csv) if tracciato_csv else FILE_CSV

    # Costruisce la configurazione DB partendo dai default e sovrascrivendo
    # solo i parametri esplicitamente forniti
    db_config = dict(DB_CONFIG)
    if host is not None:
        db_config["host"] = host
    if user is not None:
        db_config["user"] = user
    if password is not None:
        db_config["password"] = password
    if database is not None:
        db_config["database"] = database

    log.info("=== FASE 3 - Caricamento MySQL (database: intermediMC) ===")
    log.info(f"File CSV: {file_csv}")
    log.info(f"Host MySQL: {db_config['host']} | Database: {db_config['database']}")

    # Verifica file CSV
    if not file_csv.exists():
        log.error(f"File non trovato: {file_csv}")
        raise FileNotFoundError(f"File non trovato: {file_csv}")

    # Connessione MySQL
    try:
        conn = mysql.connector.connect(**db_config)
        conn.autocommit = False
        cur = conn.cursor()
        log.info("Connessione a MySQL riuscita (database: intermediMC)")
    except mysql.connector.Error as exc:
        log.error(f"Errore di connessione MySQL: {exc}")
        raise

    # Verifica tabelle vuote
    for t in ("mcputerecupubbinte", "mcrecorecuallepubb"):
        cur.execute(f"SELECT COUNT(*) FROM `{t}`")
        n = cur.fetchone()[0]
        if n > 0:
            log.warning(f"Tabella {t} contiene gia' {n} righe - procedo comunque.")

    # Lettura CSV
    df = pd.read_csv(file_csv, dtype=str, encoding="utf-8")
    totale = len(df)
    log.info(f"Righe nel tracciato di mezzo: {totale}")

    pbu_num = 1
    tot_atti = 0
    tot_docs = 0

    for _, row in df.iterrows():

        # Valori grezzi
        oggetto      = _str(row.get("oggetto"), default="")
        data_atto_s  = _valida_data(row.get("data_atto"))
        tipo_atto    = _str(row.get("tipo_atto"), maxlen=50, default="")
        numero_atto  = _str(row.get("numero_atto"), maxlen=20, default="")
        data_pub_s   = _valida_data(row.get("data_pubblicazione"))
        data_scd_s   = _valida_data(row.get("data_scadenza"))
        url_doc      = _str(row.get("url_documento"), default="")
        allegati_raw = _str(row.get("allegati"), default="")

        # Anno pubblicazione
        pbu_ann = _anno(data_pub_s, data_atto_s)

        # a. INSERT atto
        cur.execute(SQL_ATTO, (
            _enc(oggetto),
            data_atto_s,
            _enc(tipo_atto),
            _enc(numero_atto),
            data_pub_s,
            data_scd_s,
            pbu_num,
            pbu_ann,
        ))
        tot_atti += 1

        # b. INSERT documento principale
        if url_doc:
            nome_doc = _nome_da_url(url_doc)
            cur.execute(SQL_DOC, (
                pbu_num,
                pbu_ann,
                1,              # documento principale
                _enc(nome_doc),
                _enc(""),       # percorso vuoto per il doc principale
            ))
            tot_docs += 1

        # c. INSERT allegati
        if allegati_raw:
            for perc in allegati_raw.split(","):
                perc = perc.strip()
                if not perc:
                    continue
                nome_all = _nome_da_percorso(perc)
                cur.execute(SQL_DOC, (
                    pbu_num,
                    pbu_ann,
                    0,              # allegato
                    _enc(nome_all),
                    _enc(perc[:200]),
                ))
                tot_docs += 1

        # d. Incrementa progressivo
        pbu_num += 1

        # e. Commit periodico e log
        if tot_atti % COMMIT_OGNI == 0:
            conn.commit()
            log.info(f"  Inserite {tot_atti} righe su {totale} totali "
                     f"({tot_docs} documenti/allegati)")

    # Commit finale
    conn.commit()

    # Riepilogo
    log.info("-" * 50)
    log.info(f"Totale atti inseriti:               {tot_atti}")
    log.info(f"Totale documenti/allegati inseriti: {tot_docs}")
    log.info("Fine caricamento.")

    cur.close()
    conn.close()

    return {"tot_atti": tot_atti, "tot_docs": tot_docs}


# ---------------------------------------------------------------------------
# Esecuzione diretta (comportamento invariato rispetto alla versione originale)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    carica()
