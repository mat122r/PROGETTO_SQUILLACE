# Skills – Orchestratori ETL

Questa cartella contiene gli **orchestratori** che permettono di lanciare
l'intera pipeline ETL (Estrai → Normalizza → Carica) con un **singolo comando**,
passando semplicemente un file di configurazione YAML.

---

## Struttura della cartella

```
skills/   ← PUNTO DI INGRESSO UNICO (Agent-Ready)
├── run_static.py          ← Orchestratore per portali statici (BeautifulSoup)
├── run_dynamic.py         ← Orchestratore per portali dinamici (Selenium)
├── template_static.yaml   ← Template YAML commentato per portali statici
├── template_dynamic.yaml  ← Template YAML commentato per portali dinamici
├── SKILL.md               ← Manuale nativo per agenti AI (Contratto Core)
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
2. **L'agente compila il YAML, non scrive Python** – Il template YAML
   (`template_static.yaml` o `template_dynamic.yaml`) è l'unica interfaccia
   di configurazione. L'agente identifica i selettori CSS dal codice HTML
   del portale e popola il file YAML in `config/`.
3. **Zero codice Python generato da zero** – La logica di esecuzione è
   già blindata negli orchestratori `run_static.py` e `run_dynamic.py`.
   Generare nuovi scraper Python è **esplicitamente vietato** dal contratto,
   eliminando alla radice il rischio di allucinazioni, bug di sintassi e
   regressioni.

## Come aggiungere un nuovo portale

### 1. Copia il template appropriato nella cartella `config/`

**Portale statico:**
```bash
cp skills/template_static.yaml config/nuovo_portale.yaml
```

**Portale dinamico:**
```bash
cp skills/template_dynamic.yaml config/nuovo_portale_dinamico.yaml
```

### 2. Modifica il file YAML con i valori del nuovo portale

Apri il file copiato e compila i campi:

- **`name`** – Nome descrittivo del portale (es. `"Comune di Catanzaro – Albo"`).
- **`base_url`** – URL base del sito (es. `"https://albo.comune.catanzaro.it"`).
- **`list_url`** – URL relativo della pagina con la lista degli atti.
- **`table_selector`** / **`row_selector`** – Selettori CSS per la tabella e le righe.
- **`fields`** – Mappa nome campo → selettore CSS della cella.

> **Suggerimento:** Usa gli strumenti di sviluppo del browser (tasto F12) per
> identificare i selettori CSS corretti. Fai clic destro su un elemento della
> tabella e scegli "Ispeziona" per vedere la struttura HTML.

### 3. Lancia l'orchestratore

**Portale statico:**
```bash
python skills/run_static.py --config config/nuovo_portale.yaml
```

**Portale dinamico:**
```bash
python skills/run_dynamic.py --config config/nuovo_portale_dinamico.yaml
```

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
| `--db-name DATABASE` | Nome del database MySQL | `intermedimc.sql` |

### Esempi

```bash
# Pipeline completa con portale statico
python skills/run_static.py --config config/nuovo_portale.yaml

# Solo estrazione e normalizzazione (senza caricare su MySQL)
python skills/run_static.py --config config/nuovo_portale.yaml --no-load

# Pipeline dinamica con credenziali MySQL personalizzate
python skills/run_dynamic.py --config config/portale_dinamico.yaml \
    --db-host 192.168.1.10 --db-user etl_user --db-password secret

# Pipeline statica con percorsi di output personalizzati
python skills/run_static.py --config config/nuovo_portale.yaml \
    --output-csv data/nuovo_portale_raw.csv \
    --tracciato data/nuovo_portale_tracciato.csv

# Pipeline in modalità INCREMENTALE (Isolamento dei soli nuovi atti)
python skills/run_static.py --config config/nuovo_portale.yaml --incremental

# Solo estrazione dinamica incrementale senza caricamento DB
python skills/run_dynamic.py --config config/portale_dinamico.yaml --incremental --no-load
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
- Credenziali di default: utente `root`, nessuna password

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

*Skills create il 3 giugno 2026 nell'ambito del Progetto Squillace – Pipeline ETL. Ultima revisione: 3 giugno 2026.*
