# Progetto Squillace – Pipeline ETL

Pipeline ETL per estrarre atti amministrativi da portali comunali, normalizzarli e
caricarli su MySQL. Supporta portali statici (BeautifulSoup) e dinamici (Selenium),
scala a N comuni modificando solo un file YAML, zero codice Python da scrivere.

---

## 🚀 START HERE — Avvio rapido in 4 passi

> Prima di leggere qualsiasi altra cosa, esegui questi comandi nell'ordine.

**Prerequisiti (una volta sola):**
1. Avvia **XAMPP** → Start MySQL
2. Apri HeidiSQL → importa `intermediMC.sql` → si crea il database `intermediMC`

**Da terminale nella cartella del progetto:**

```bash
# 1. Installa le dipendenze
pip install -r requirements.txt

# 2. Verifica che tutto sia pronto
python skills/run_pipeline.py --check

# 3. Prima estrazione completa (E → T → L per tutti i comuni)
python skills/run_pipeline.py

# 4. Aggiornamenti successivi
# Accoda i nuovi atti al DB senza svuotarlo:
python skills/run_pipeline.py --incremental --append

# Oppure, per forzare lo svuotamento totale delle tabelle MySQL:
python skills/run_pipeline.py --truncate
```

> ⚠️ Il server ASMENET impiega 4-5 minuti per rispondere. Il processo non è bloccato: attendi senza interrompere.

---

## 🗺️ Mappa dei file — cosa leggere e in che ordine

| Priorità | File | Cosa contiene |
|----------|------|---------------|
| **1° LEGGI** | Questo file | Struttura del progetto, fasi E/T/L, istruzioni complete |
| **2° LEGGI** | [`DIARIO_PROCESSO.md`](DIARIO_PROCESSO.md) | Come è stato sviluppato, errori corretti, guida al riutilizzo |
| **3° se usi skills** | [`skills/README.md`](skills/README.md) | Come aggiungere nuovi portali, opzioni avanzate CLI |
| **Solo per agenti AI** | [`skills/SKILL.md`](skills/SKILL.md) | Contratto operativo macchina-leggibile |
| **Config fonti** | [`config/sources.yaml`](config/sources.yaml) | Unico file da modificare per aggiungere comuni |

---

## 📁 Perché questi file sono separati — la logica della documentazione

Il progetto adotta una documentazione multi-file: ogni documento ha un'audience specifica e un contenuto esclusivo, così da non mescolare livelli diversi di lettura.

| File | Audience | Perché esiste |
|------|----------|-----------------|
| **`README.md`** (questo) | Umano — primo approccio | Orientamento rapido: struttura, fasi E/T/L, come avviare la pipeline. È il punto di ingresso per chiunque scopra il progetto per la prima volta. |
| **`DIARIO_PROCESSO.md`** | Umano — revisore del processo | Racconta *come* è stato sviluppato: quale agente, dove ha sbagliato, come è stato corretto e verificato. Documento narrativo, non operativo. |
| **`skills/README.md`** | Umano tecnico che vuole estendere il sistema | Guida operativa step-by-step per aggiungere un nuovo comune o portale. Sta in `skills/` perché è la documentazione del modulo riutilizzabile. |
| **`skills/SKILL.md`** | **Agente AI (coding agent)** | Contratto macchina-leggibile: trigger di attivazione, workflow obbligatorio, regole MUST. L'agente lo legge *prima* di qualsiasi operazione. È il motivo per cui la prossima volta che arriva un caso simile basta un prompt, non un progetto da zero. |

> **In sintesi:** `README.md` spiega *cosa è*. `DIARIO_PROCESSO.md` racconta *come è stato fatto*. `skills/README.md` insegna *come estenderlo*. `skills/SKILL.md` *fa operare l'agente AI* senza intervento umano.

---

## 🤖 Agenti AI utilizzati

| Agente / Modello | Ruolo nel progetto |
|------------------|-------------------|
| **Antigravity** (Claude Sonnet 4.6, Gemini 3.1 Pro High, Gemini 3.5 Flash High) | Sviluppatore e orchestratore principale. Ha generato la struttura iniziale E/T/L, scritto gli scraper, progettato il tracciato di mezzo e costruito l'ecosistema Agent-Ready. |
| **DeepSeek** | Revisore critico. Ha verificato il codice prodotto da Antigravity, analizzato i log di esecuzione, suggerito correzioni e monitorato la coerenza tra tracciato di mezzo e tabelle MySQL. |

### Errori e correzioni (sintesi)

Durante lo sviluppo sono stati identificati e corretti diversi bug critici:
- **Crash su installazione pulita**: la normalizzazione dipendeva dai singoli
  sotto-orchestratori. Risolto centralizzando le fasi T e L nel Master Orchestrator.
- **Nomi file PDF corrotti (mojibake)**: l'encoding delle pagine non veniva forzato,
  producendo caratteri illeggibili nei nomi dei file. Risolto con `response.encoding = 'utf-8'`
  e sanitizzazione avanzata dei filename.
- **Sovrascrittura e crash MySQL**: le tabelle venivano popolate senza controllare
  lo stato esistente. Risolto aggiungendo i flag `--truncate` e `--append`.
- **Credenziali hardcoded**: host, utente e password erano fissi nel codice.
  Risolto centralizzando la configurazione in `config/sources.yaml`.

> Per il dettaglio tecnico completo di tutti i bug e delle risoluzioni, si veda il
> **[DIARIO_PROCESSO.md](DIARIO_PROCESSO.md)**.

---

## Struttura del progetto

Tutti i file sono organizzati in cartelle che rispecchiano le tre fasi della pipeline (E, T, L), più una cartella per la configurazione e una per i dati.

### Cartella principale
- `README.md`
- `requirements.txt`
- `intermediMC.sql`
- `.antigravityrules` ← regole di workspace per agenti AI
- `.cursorrules` ← regole di workspace per Cursor/Copilot

### config/
- `sources.yaml` ← configurazioni delle fonti esistenti

### skills/   ← PUNTO DI INGRESSO UNICO (Agent-Ready)
- `run_pipeline.py` ← **MASTER ORCHESTRATOR** – lancia tutta la pipeline multifonte con un comando
- `run_static.py` ← sotto-orchestratore per portali statici (usato dal Master)
- `run_dynamic.py` ← sotto-orchestratore per portali dinamici (usato dal Master)
- `template_static.yaml` ← template YAML commentato per portali statici
- `template_dynamic.yaml` ← template YAML commentato per portali dinamici
- `SKILL.md` ← manuale nativo per agenti AI
- `README.md` ← guida operativa per utenti umani

### scrapers/
- `base_scraper.py`
- `fonte1_scraper.py`
- `fonte2_scraper.py`

### transform/
- `normalizza.py`

### load/
- `carica_mysql.py`

### data/
- `fonte1_raw.csv`
- `fonte2_raw.csv`
- `tracciato_mezzo.csv`
- `.last_run_static.json` ← stato incrementale portali statici
- `.last_run_dynamic.json` ← stato incrementale portali dinamici

### allegati/
- `fonte1/` (PDF primo portale)
- `fonte2/` (PDF secondo portale)

---

## Fase 1 – Estrazione

### Obiettivo
Recuperare tutti gli atti pubblicati dal primo portale e solo le delibere
dal 12/04/2024 dal secondo portale, compresi gli allegati.

### Analisi preliminare dei portali
Prima di scrivere qualsiasi codice, abbiamo aperto i due siti nel browser e
studiato l'HTML con gli strumenti di sviluppo (F12). Per ogni fonte abbiamo
individuato:

- La struttura della tabella o del contenitore dei dati
- I selettori CSS per estrarre numero, data, oggetto, tipo e link al dettaglio
- Come vengono gestiti gli allegati (link diretti, script di download, ecc.)
- Se la pagina è statica o carica i dati dinamicamente
- Il meccanismo di paginazione (dove presente)

### Fonte 1 – Portale statico (tutti i dati)
Il primo portale presenta un archivio storico di 3726 record in una **singola
pagina HTML**, senza paginazione. La tabella è molto grande ma completamente
statica, quindi è stato possibile usare `requests` e `BeautifulSoup` per
scaricare la pagina e fare il parsing.

**Scelte tecniche:**
- La pagina è molto pesante, quindi abbiamo aumentato il timeout HTTP a 120 secondi.
- Gli allegati si trovano su una seconda pagina di dettaglio (raggiungibile
  tramite un link nella tabella principale). Per ogni atto lo scraper visita
  il dettaglio e scarica i PDF.
- Gli allegati vengono salvati in `allegati/fonte1/<N.Reg>/`, organizzati per
  numero di registrazione, in modo che sia sempre possibile risalire dal
  record al file.

**Atti annullati:**
Come anticipato, gli atti annullati sono stati estratti insieme agli altri
e rimossi nella fase di normalizzazione.

### Fonte 2 – Portale dinamico (solo delibere dal 12/04/2024)
Il secondo portale ha una tabella che viene **caricata dinamicamente via
JavaScript** dopo il caricamento della pagina. Con `requests` si otteneva solo
lo scheletro vuoto della pagina, senza dati.

**Scelta di Selenium:**
Abbiamo usato **Selenium** con Chrome in modalità headless per simulare un
browser reale e attendere il caricamento completo della tabella. Questo ha
risolto il problema del contenuto dinamico.

**Filtri applicati:**
- **Data:** lo scraper naviga tutte le pagine dello storico e scarta
  automaticamente le delibere con data anteriore al 12/04/2024.
- **Tipo:** vengono tenute solo le righe il cui campo "Tipo" contiene la
  parola "Delibere" (quindi "Delibere di Giunta" e "Delibere di Consiglio").

**Allegati:**
Anche qui gli allegati vengono scaricati dalla pagina di dettaglio e salvati
in `allegati/fonte2/<Numero atto>/`. Il riferimento è tracciabile dal CSV.


---

## Fase 2 – Normalizzazione

### Obiettivo
Creare un tracciato di mezzo unico che unifichi i dati delle due fonti,
applicando tutte le pulizie necessarie.

### Perché un tracciato di mezzo
È stato richiesto esplicitamente uno strato intermedio che disaccoppi
l'estrazione dal caricamento. Il tracciato di mezzo è un CSV con una
struttura fissa e indipendente dalle fonti: se in futuro si aggiungerà un
nuovo portale, basterà aggiornare lo scraper e la normalizzazione, senza
toccare il caricamento su MySQL.

### Operazioni di pulizia effettuate

**Fonte 1 – Rimozione atti annullati:**
Abbiamo filtrato via tutti i record con `link_dettaglio` vuoto (che sono
proprio gli atti annullati) e quelli con `numero_reg` che inizia per
"Pubblicazione" (le righe di spiegazione). In totale sono state rimosse
262 righe.

**Fonte 2 – Estrazione del tipo atto:**
Come accennato, il parsing è stato corretto per estrarre solo la parte
dopo `"Tipo\n"`.

**Date e codifica:**
Tutte le date sono state convertite in formato `YYYY-MM-DD`. L'encoding
è UTF-8 su tutti i CSV.

### Struttura del tracciato di mezzo
Il CSV finale contiene 10 colonne comuni: `id_fonte`, `numero_pubblicazione`,
`tipo_atto`, `numero_atto`, `data_atto`, `oggetto`, `data_pubblicazione`,
`data_scadenza`, `url_documento`, `allegati`. Ogni campo è mappato dalle
colonne originali delle due fonti (dove disponibile).

Il tracciato di mezzo contiene **4.055 righe totali** (3.595 dalla Fonte 1
e 460 dalla Fonte 2).

---

## Fase 3 – Load su MySQL

### Obiettivo
Popolare il database MySQL `intermediMC` con i dati del tracciato di mezzo.

### Preparazione dell'ambiente
Abbiamo utilizzato **XAMPP** per avviare un server MySQL in locale. Dopo aver
risolto un problema tecnico con i file di log di InnoDB che impedivano l'avvio
di MySQL, il server è partito correttamente sulla porta **3306**.

Tramite **HeidiSQL** ci siamo connessi al server (`localhost:3306`, utente
`root`, password `admin`) e abbiamo importato il file `intermediMC.sql` per
creare il database e le tabelle necessarie. Le tabelle sono state create
vuote e pronte per essere popolate.

### Credenziali DB centralizzate
Le credenziali del database non sono più hardcoded nel codice. Possono essere
modificate all'interno del file `config/sources.yaml` nel blocco `database:`.
In un ambiente di produzione, si raccomanda di non versionare credenziali reali.

### Script di caricamento
Lo script `load/carica_mysql.py`:
1. Viene chiamato dal Master Orchestrator una sola volta al termine di tutte le estrazioni.
2. Si connette a MySQL utilizzando le credenziali definite in `config/sources.yaml`.
3. Legge il tracciato di mezzo con pandas.
4. Se le tabelle non sono vuote, blocca il processo a meno che non si usino i flag:
   - `--truncate`: svuota le tabelle e riparte col progressivo 1.
   - `--append`: calcola il `MAX(MCRECU_PBU_NUM)` dell'anno e accoda i nuovi record.
5. Inserisce i record nelle tabelle collegate `mcputerecupubbinte` (atti) e `mcrecorecuallepubb` (allegati).

### Risultato finale
- **4.055 atti** inseriti in `mcputerecupubbinte`
- **9.159 documenti/allegati** inseriti in `mcrecorecuallepubb`
- La terza tabella (`mcreterecuanag`) è rimasta vuota perché non avevamo
  dati anagrafici da inserire.

---



---
*Progetto personale realizzato da Mattia Cannavò | Terminato il 29 maggio 2026, revisionato il 5 giugno 2026*

> Per il racconto dettagliato del processo di sviluppo, degli errori corretti e della strategia di verifica, leggi [`DIARIO_PROCESSO.md`](DIARIO_PROCESSO.md).
