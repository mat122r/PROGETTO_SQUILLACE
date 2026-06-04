# Skills – Orchestratori ETL

Questa cartella contiene gli **orchestratori** che permettono di lanciare
l'intera pipeline ETL (Estrai → Normalizza → Carica) con un **singolo comando**,
passando semplicemente un file di configurazione YAML.

---

## Struttura della cartella

```
skills/   ← PUNTO DI INGRESSO UNICO (Agent-Ready)
├── run_pipeline.py        ← MASTER ORCHESTRATOR (Lancia tutta la pipeline multifonte)
├── run_static.py          ← Sotto-orchestratore per portali statici
├── run_dynamic.py         ← Sotto-orchestratore per portali dinamici
├── template_static.yaml
├── template_dynamic.yaml
├── SKILL.md               ← Manuale nativo per agenti AI
└── README.md              ← Questo file
```

---

## Portale statico vs portale dinamico

| Caratteristica | Portale statico | Portale dinamico |
|----------------|-----------------|------------------|
| Tecnologia | `requests` + `BeautifulSoup` | `Selenium` + Chrome headless |
| Contenuto pagina | HTML completo al primo caricamento | Dati caricati via JavaScript |
| Velocità | Più rapido | Più lento (avvia un browser reale) |
| Esempio reale | ASMENET (albosquillace.asmenet.it) | Halley (portale5.halleysud.it) |
| Orchestratore | `run_static.py` | `run_dynamic.py` |
| Template YAML | `template_static.yaml` | `template_dynamic.yaml` |

> **Come capire se un portale è dinamico?**
> Apri il portale nel browser, poi disabilita JavaScript (DevTools → Settings →
> Debugger → "Disable JavaScript") e ricarica la pagina. Se la tabella scompare
> o rimane vuota, il portale è dinamico e richiede Selenium.

---

## Integrazione Nativa con i Coding Agent

La struttura basata su file YAML **è l'interfaccia contrattuale attiva**
con cui un agente AI (come Antigravity) consuma questo modulo come una
**Skill**. Non si tratta di un'ipotesi futura: il file `SKILL.md` definisce
le regole vincolanti che l'agente deve leggere prima di operare.

Il contratto stabilisce tre punti fermi:

1. **L'agente legge `SKILL.md`** – Prima di qualsiasi operazione, l'agente
   carica le regole del Contratto Core, che definiscono workflow, strumenti
   disponibili e regole vincolanti.
2. **L'agente aggiunge una sezione in `config/sources.yaml`** – L'unica
   interfaccia di configurazione è `config/sources.yaml`. L'agente identifica
   i selettori CSS con F12 sul browser e aggiunge una nuova sezione `fonteN:`
   con i valori del nuovo comune. Non crea mai file YAML separati.
3. **Zero codice Python generato da zero** – La logica di esecuzione è
   già blindata nel Master Orchestrator `run_pipeline.py` e nei suoi
   sotto-moduli. Generare nuovi scraper Python è **esplicitamente vietato**
   dal contratto, eliminando alla radice il rischio di allucinazioni, bug
   di sintassi e regressioni.

## Come aggiungere un nuovo portale

### 1. Usa F12 per identificare il tipo di portale

Apri il portale nel browser → disabilita JavaScript (DevTools → "Disable JavaScript") → ricarica.
- Tabella **visibile** → portale **statico** → `tipo: "static"`
- Tabella **scomparsa** → portale **dinamico** → `tipo: "dynamic"`

> I template `template_static.yaml` e `template_dynamic.yaml` nella cartella `skills/`
> sono disponibili come **riferimento commentato** per capire tutti i campi disponibili.

### 2. Aggiungi una nuova sezione in `config/sources.yaml`

Apri `config/sources.yaml` e aggiungi in fondo una nuova sezione `fonteN:`
con i selettori CSS identificati con F12:

```yaml
fonte3:                                    # ← incrementa il numero
  tipo: "static"                           # oppure "dynamic"
  name: "Comune di Catanzaro – Albo"
  base_url: "https://albo.comune.catanzaro.it"
  list_url: "/archivio/cerca.php"
  table_selector: "table.tablesorter"      # trovato con F12
  row_selector: "tbody tr"
  fields:
    numero_reg:         "td:nth-child(1)"
    tipo:               "td:nth-child(2)"
    oggetto:            "td:nth-child(4)"
    data_pubblicazione: "td:nth-child(5)"
    data_scadenza:      "td:nth-child(6)"
    link_dettaglio:     "td:nth-child(7) a"
```

### 3. Lancia il Master Orchestrator

```bash
# Prima esecuzione completa (tutti i comuni incluso il nuovo)
python skills/run_pipeline.py

# Aggiornamenti periodici
python skills/run_pipeline.py --incremental
```

Il sistema rileva automaticamente `fonte3` e la include nella progressione `[3/3]`.
**Non serve toccare nessun file Python.**

---

## Opzioni da riga di comando

Entrambi gli orchestratori accettano le stesse opzioni:

| Opzione | Descrizione | Default |
|---------|-------------|---------|
| `--config PERCORSO` | **(obbligatorio)** Percorso del file YAML | – |
| `--incremental` | Esecuzione incrementale: processa solo i nuovi atti (delta) | off |
| `--output-csv PERCORSO` | Percorso del CSV grezzo di output | `data/fonte1_raw.csv` (static) / `data/fonte2_raw.csv` (dynamic) |
| `--tracciato PERCORSO` | Percorso del tracciato di mezzo | `data/tracciato_mezzo.csv` |
| `--no-normalize` | Salta la fase di normalizzazione | off |
| `--no-load` | Salta il caricamento su MySQL | off |
| `--db-host HOST` | Host MySQL | `localhost` |
| `--db-user UTENTE` | Utente MySQL | `root` |
| `--db-password PASSWORD` | Password MySQL | *(vuota)* |
| `--db-name DATABASE` | Nome del database MySQL | `intermediMC` |

### Esempi

```bash
# =======================================================================
# USO NORMALE — Master Orchestrator (tutte le fonti in un colpo solo)
# =======================================================================

# Pipeline completa: E → T → L per tutti i comuni in sources.yaml
python skills/run_pipeline.py

# Solo nuovi atti (incrementale) per tutti i comuni
python skills/run_pipeline.py --incremental

# Verifica ambiente senza eseguire la pipeline
python skills/run_pipeline.py --check

# Estrazione + normalizzazione senza caricare su MySQL
python skills/run_pipeline.py --no-load

# =======================================================================
# USO AVANZATO — Sotto-orchestratori singoli (per debug o test isolati)
# =======================================================================

# Testa un singolo portale statico senza toccare sources.yaml
python skills/run_static.py --config config/sources.yaml --no-load

# Testa un singolo portale dinamico con credenziali MySQL personalizzate
python skills/run_dynamic.py --config config/sources.yaml \
    --db-host 192.168.1.10 --db-user etl_user --db-password secret

# Modalità incrementale su singola fonte
python skills/run_static.py --config config/sources.yaml --incremental --no-load
```

---

## Riepilogo della pipeline

```
YAML config
    │
    ▼
[Opzione --incremental (Check File Stato JSON)]
    Legge data/.last_run_static.json o data/.last_run_dynamic.json
    → Se attivo: filtra gli atti già processati, procede solo con il delta
    │
    ▼
[FASE 1] Estrazione
    Fonte1Scraper (static) / Fonte2Scraper (dynamic)
    → produce: data/fonte1_raw.csv  o  data/fonte2_raw.csv
    │
    ▼
[FASE 2] Normalizzazione
    transform/normalizza.normalizza()
    → produce: data/tracciato_mezzo.csv
    │
    ▼
[FASE 3] Caricamento MySQL
    load/carica_mysql.carica()
    → popola: mcputerecupubbinte + mcrecorecuallepubb
```

---

## Requisiti

### Python
```
Python >= 3.9
```

### Dipendenze Python
```bash
pip install -r requirements.txt
```

Le dipendenze principali sono:
- `requests`, `beautifulsoup4`, `lxml` – scraping statico
- `selenium`, `webdriver-manager` – scraping dinamico
- `pandas` – normalizzazione CSV
- `mysql-connector-python` – caricamento MySQL
- `pyyaml` – lettura dei file di configurazione

### Database MySQL
- MySQL in esecuzione su `localhost:3306`
- Schema importato da `intermediMC.sql`
- Credenziali di default: utente `root`,  password: `admin`

### Per portali dinamici
- **Google Chrome** installato (qualsiasi versione recente)
- `webdriver-manager` si occupa automaticamente di scaricare il ChromeDriver corretto

---

## Risoluzione problemi

| Problema | Possibile causa | Soluzione |
|----------|----------------|-----------|
| `File di configurazione non trovato` | Percorso YAML errato | Verificare il percorso con `--config` |
| `Campi obbligatori mancanti nel file YAML` | Template incompleto | Controllare i campi richiesti nel template |
| `Could not find table with selector` | Selettore CSS errato | Rivedere i selettori con F12 nel browser |
| `Errore di connessione MySQL` | MySQL non avviato o credenziali errate | Avviare XAMPP/MySQL e verificare le credenziali |
| `ModuleNotFoundError` | Dipendenze non installate | Eseguire `pip install -r requirements.txt` |
| Tabella vuota con Selenium | JavaScript non caricato | Aumentare `selenium_timeout` nel YAML |

---

*Progetto Squillace – Pipeline ETL | Mattia Cannavò | Progetto terminato il 29 maggio 2026, revisionato per l'ultima volta il 3 giugno 2026.*
