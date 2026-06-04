# DIARIO DI PROCESSO – Pipeline ETL Portali Comunali
### Progetto Squillace – Pipeline ETL per Portali Comunali
*Realizzato da Mattia Cannavò | 29 maggio – 4 giugno 2026*

> **A cosa serve questo documento**
> Questo diario risponde alla domanda *"come hai lavorato con l'agente AI?"*
> Non è una guida tecnica (quella è in [`README.md`](../README.md) e [`skills/README.md`](README.md)),
> né un contratto per agenti AI (quello è in [`skills/SKILL.md`](SKILL.md)).
> È un documento narrativo: quale agente ho usato, come ho impostato la collaborazione,
> dove ha sbagliato e come l'ho corretto, come ho verificato l'output finale.

---

## 1. DIARIO DI BORDO SVILUPPO

### Agenti utilizzati e ruoli

| Agente | Ruolo nel progetto |
|--------|--------------------|
| **Antigravity** (Claude Sonnet 4.6) | Sviluppatore e orchestratore principale. Ha generato la struttura iniziale dell'architettura E/T/L, scritto gli scraper, progettato il tracciato di mezzo, implementato il caricamento MySQL e costruito l'intero ecosistema Agent-Ready (`skills/`, template YAML, regole di workspace). |
| **DeepSeek** | Revisore critico. Ha verificato il codice prodotto da Antigravity, analizzato i log di esecuzione, suggerito correzioni sui filtri e monitorato la coerenza tra il tracciato di mezzo e le tabelle MySQL. Ha svolto il ruolo di "quality gate" umano sul lavoro dell'agente. |

### Come abbiamo impostato il lavoro

Il lavoro è stato scomposto in tre fasi distinte fin dall'inizio, tenendo i moduli
completamente separati così che un errore in una fase non impattasse le altre:

```
FASE E – Estrazione    →  scrapers/
FASE T – Trasformazione →  transform/normalizza.py
FASE L – Caricamento    →  load/carica_mysql.py
```

Il punto di svolta architetturale è avvenuto durante la fase di revisione critica del progetto. Abbiamo capito che non bastava avere
codice funzionante: serviva un **ecosistema riutilizzabile da un agente AI**.

Abbiamo introdotto:
- `skills/SKILL.md` – contratto operativo macchina-leggibile (trigger, workflow, regole MUST)
- `skills/template_static.yaml` e `skills/template_dynamic.yaml` – interfacce dichiarative
- `skills/run_pipeline.py` – Master Orchestrator, unico punto di ingresso
- `.antigravityrules` / `.cursorrules` – guardrail permanenti iniettati in ogni sessione agente

Con questo approccio, l'agente non genera mai nuovo codice Python: legge `SKILL.md`,
compila un YAML e lancia un comando. Zero rischio di allucinazioni sintattiche, zero
regressioni sul codice core.

---

## 2. REGISTRO ERRORI E CORREZIONI

### Errori della fase di sviluppo iniziale

**Atti annullati – gestione spostata in normalizzazione**
Il tentativo di escludere gli atti annullati direttamente in fase di scraping non ha
funzionato: lo stile barrato (`text-decoration: line-through`) era applicato alle
singole celle, non alla riga intera. La soluzione è stata filtrare in fase T tutti
i record con `link_dettaglio` vuoto, che corrispondono esattamente agli annullati.
Rimossi 262 record in fase di normalizzazione.

**Timeout HTTP insufficiente per ASMENET**
Il portale ASMENET restituisce una singola pagina HTML da ~4 MB contenente 3.857
righe. Il timeout predefinito di 30 secondi causava errori intermittenti. Portato
a 120 secondi dopo analisi dei tempi di risposta del server.

**Regex tipo atto – Fonte 2**
La seconda fonte (Halley) include nel campo `tipo` un blocco di testo multiriga del
tipo `"579\n\nMittente\nCOMUNE DI SQUILLACE\n\nTipo\nDelibere di Giunta"`. La prima
regex estratta non isolava correttamente la parte dopo `"Tipo\n"`. Corretta con la
funzione `_estrai_tipo_halley()` in `transform/normalizza.py`.

---

### 🔴 CRITICAL FIXES – Sessione 3 giugno 2026

Questi quattro bug sono stati identificati e corretti nella fase di stabilizzazione
finale, dopo i primi test di esecuzione incrementale centralizzata.

---

**BUG 1 – Disallineamento chiave incrementale in `fonte1_scraper.py`**

*Sintomo:* In modalità `--incremental`, lo scraper ASMENET non si fermava mai al
primo record già processato. Scansionava l'intera tabella (3.857 righe) invece di
fare break immediato.

*Causa radice:* Lo scraper costruiva la chiave per l'early exit come
`numero_reg||data_pubblicazione`, ma il file di stato `.last_run_static.json`
memorizzava le chiavi come solo `numero_reg`. Il mismatch faceva sì che nessuna
chiave matchasse mai.

*Fix:*
```python
# PRIMA (mai matchava):
current_key = f"{numero_reg}||{data_pubblicazione}"

# DOPO (allineato con _build_key di run_static.py):
current_key = str(numero_reg).strip()
```

*Risultato:* In modalità incrementale, lo scraper fa ora break al primo record
già processato, senza analizzare le righe successive né fare richieste di dettaglio.

---

**BUG 2 – Timeout di rete bloccava l'intera pipeline**

*Sintomo:* Se il server ASMENET era irraggiungibile, l'eccezione si propagava fino
al Master Orchestrator che terminava con errore fatale, impedendo l'esecuzione di
Fonte 2 (Halley).

*Causa radice:* `fetch_page()` in `base_scraper.py` catturava tutte le eccezioni
in un unico `except Exception` e le rilanciava dopo i retry, senza distinguere tra
errori di rete (recuperabili) e errori HTTP (fatali).

*Fix:*
```python
# Gestione separata per tipo di errore:
except requests.exceptions.Timeout:
    ...
    return None  # Non blocca: l'orchestratore gestisce None e prosegue

except requests.exceptions.ConnectionError:
    ...
    return None  # Stessa logica
```

Negli orchestratori:
```python
except ConnectionError as exc:
    print(f"\n[AVVISO RETE] {exc}")
    sys.exit(0)  # exit(0) = uscita pulita, pipeline continua con fonte successiva
```

*Risultato:* Se ASMENET non risponde, Halley viene processata comunque. Il Master
Orchestrator non si blocca mai su un singolo server.

---

**BUG 3 – UnicodeEncodeError su console Windows**

*Sintomo:* La pipeline terminava con `UnicodeEncodeError: 'charmap' codec can't
encode character '\u2713'` alla stampa del messaggio finale (`✓`). I terminali
Windows usano `cp1252` come encoding predefinito, che non supporta caratteri
Unicode al di fuori del Basic Latin.

*Fix:*
```python
# Aggiunto all'inizio di ogni script:
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Nei subprocess del Master Orchestrator:
_env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
res_static = subprocess.run(cmd_static, env=_env)
```

*Risultato:* Output pulito su qualsiasi terminale Windows senza crash.

---

**BUG 4 – Logging su stderr → NativeCommandError → EXIT CODE: 1**

*Sintomo:* La pipeline completava con successo e stampava il messaggio finale, ma
PowerShell riportava `EXIT CODE: 1` (errore). Ogni esecuzione veniva classificata
come fallita anche quando era corretta.

*Causa radice:* `base_scraper.py` chiamava `logging.basicConfig()` a livello di
modulo. Poiché Python esegue il codice dei moduli all'import, e `base_scraper.py`
viene importato prima che `run_static.py` possa configurare il proprio logging,
il root logger veniva configurato su `stderr` (default di `basicConfig`). Tutti i
log successivi andavano su stderr, che PowerShell interpreta come errore fatale
(`NativeCommandError`).

*Fix:*
```python
# RIMOSSO da base_scraper.py:
logging.basicConfig(level=logging.INFO, format='...')  # ← configurava su STDERR

# MANTENUTO solo:
logger = logging.getLogger(__name__)
# La configurazione è responsabilità esclusiva degli orchestratori
```

*Risultato:* Tutti i log vanno su stdout. PowerShell non rileva stderr.
`EXIT CODE: 0` pulito su ogni esecuzione corretta.

---

## 3. STRATEGIA DI VERIFICA QUALITÀ

La correttezza dell'output è stata verificata su 4 livelli indipendenti:

### Livello 1 – Metriche in tempo reale (log a schermo)

Ogni fase stampa contatori espliciti durante l'esecuzione:
```
Found 3857 rows in the list table.
Dopo rimozione link vuoti:      3595  (rimossi 262)
Totale righe nel tracciato:     4055
Atti inseriti:                  4055
Documenti/allegati inseriti:    9159
```
Un disallineamento tra questi numeri segnala immediatamente un problema.

### Livello 2 – Ispezione CSV a campione

Dopo ogni fase, i CSV prodotti (`fonte1_raw.csv`, `fonte2_raw.csv`,
`tracciato_mezzo.csv`) sono stati aperti in VS Code e controllati a campione:
- Date nel formato corretto `YYYY-MM-DD`
- Nessun campo `NaN` nei campi obbligatori
- Tipo atto estratto correttamente per Fonte 2
- Percorsi allegati coerenti con la struttura `allegati/fonte1/<N.Reg>/`

### Livello 3 – Query SQL di riscontro

Dopo il caricamento, sono state eseguite query di verifica su MySQL:
```sql
SELECT COUNT(*) FROM mcputerecupubbinte;          -- atteso: 4055
SELECT COUNT(*) FROM mcrecorecuallepubb;          -- atteso: 9159
SELECT MCRECU_PBU_ANN, COUNT(*) FROM mcputerecupubbinte
  GROUP BY MCRECU_PBU_ANN ORDER BY MCRECU_PBU_ANN;  -- distribuzione per anno
```
I conteggi hanno confermato la corrispondenza con il tracciato di mezzo.

### Livello 4 – Verifica fisica degli allegati

Controllo che i percorsi nel CSV puntassero a file effettivamente esistenti:
```
allegati/fonte1/0001-2024/delibera.pdf  ← file esiste? ✓
allegati/fonte2/42/Delibera_n_42_Documento_Principale.pdf  ← file esiste? ✓
```
Campione di 20 record verificati manualmente. Tutti i percorsi risolti correttamente.

---

*Fine diario di processo. Ultima revisione: 4 giugno 2026.*

