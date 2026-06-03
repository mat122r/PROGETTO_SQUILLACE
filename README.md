# Progetto Squillace – Pipeline ETL

Questo documento racconta l'intero percorso che ha portato alla realizzazione della
pipeline ETL per il Comune di Squillace: dall'analisi dei portali fino al caricamento
dei dati nel database MySQL, passando per tutte le difficoltà incontrate e le scelte
fatte per superarle.

---

## Agenti AI utilizzati

| Agente / Modello | Ruolo nel progetto |
|------------------|-------------------|
| **Antigravity** (con Claude Sonnet e Gemini 3.5 Flash High) | Ha generato la struttura iniziale del codice e i primi script funzionanti. È stato il punto di partenza per tutte e tre le fasi. |
| **DeepSeek** | Ha accompagnato l'intero sviluppo come supporto critico: ha verificato il codice, suggerito correzioni, aiutato a interpretare i log e monitorato la coerenza dei dati. Ha svolto il ruolo di "revisore" del lavoro di Antigravity. |

### Errori e correzioni

Durante lo sviluppo, gli agenti hanno commesso alcune piccole imprecisioni
che sono state individuate e corrette strada facendo:

- **Atti annullati**: in fase di scraping, il tentativo di escludere subito
  gli atti annullati non ha funzionato perché lo stile barrato era applicato
  alle celle e non alla riga intera. Si è quindi deciso di rimandare la
  pulizia alla normalizzazione, dove è più semplice filtrare i record senza
  link al dettaglio.
- **Timeout HTTP**: il timeout predefinito non bastava per scaricare la
  pagina più grande ed è stato portato a 120 secondi.
- **Parsing del tipo atto**: per la seconda fonte è stato necessario
  correggere l'espressione regolare per estrarre solo il testo dopo
  `"Tipo\n"`.

In tutti i casi, la verifica manuale dei log e dei CSV ha permesso di
confermare la bontà delle correzioni prima di procedere.

---

## Struttura del progetto

Tutti i file sono organizzati in cartelle che rispecchiano le tre fasi della pipeline (E, T, L), più una cartella per la configurazione e una per i dati.

### Cartella principale
- `README.md`
- `requirements.txt`
- `intermediMC.sql`

### config/
- `sources.yaml`

### scrapers/
- `base_scraper.py`
- `fonte1_scraper.py`
- `fonte2_scraper.py`

### extract/
- `estrai_fonte1.py`
- `estrai_fonte2.py`

### transform/
- `normalizza.py`

### load/
- `carica_mysql.py`
- `check_db.py`
- `check_schema.py`

### data/
- `fonte1_raw.csv`
- `fonte2_raw.csv`
- `tracciato_mezzo.csv`

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


## Estrazione incrementale (opzione futura)

Al momento la pipeline esegue un'estrazione completa a ogni esecuzione.
Per aggiungere l'estrazione incrementale (solo nuovi atti), gli orchestratori
possono essere estesi con un flag `--incremental` che:

- Salvi l'ultimo ID o data processata in un file di stato (es. `.last_run`).
- Modifichi lo scraper per riprendere da quel punto.
- In normalizzazione, aggiunga i nuovi record senza duplicati.

Questa funzionalità non è ancora implementata, ma la struttura modulare del
progetto la rende un'estensione naturale per una release successiva.


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
`root`, senza password) e abbiamo importato il file `intermediMC.sql` per
creare il database e le tabelle necessarie. Le tabelle sono state create
vuote e pronte per essere popolate.

### Nota sulle credenziali
In questo progetto non è stato usato un file `.env` per
proteggere le credenziali del database perché, trattandosi di un ambiente
di sviluppo locale con credenziali di default (`root` senza password), non
c'erano dati sensibili da proteggere. In un ambiente di produzione, le
credenziali andrebbero inserite in un file `.env` separato ed escluso dal
versionamento tramite `.gitignore`.

### Script di caricamento
Lo script `load/carica_mysql.py`:
1. Si connette a MySQL su `localhost:3306` (utente `root`, senza password).
2. Legge il tracciato di mezzo con pandas.
3. Per ogni riga, genera un numero progressivo di pubblicazione e calcola
   l'anno di riferimento.
4. Inserisce un record nella tabella `mcputerecupubbinte` (atti).
5. Per ogni atto, inserisce il documento principale e gli allegati nella
   tabella `mcrecorecuallepubb`, collegandoli tramite la coppia
   `(PBU_NUM, PBU_ANN)`.

### Risultato finale
- **4.055 atti** inseriti in `mcputerecupubbinte`
- **9.159 documenti/allegati** inseriti in `mcrecorecuallepubb`
- La terza tabella (`mcreterecuanag`) è rimasta vuota perché non avevamo
  dati anagrafici da inserire.

---

## Verifica e controllo qualità

La correttezza del lavoro è stata verificata in più passaggi, sia automatici
che manuali:

- **Durante l'estrazione:** i log mostravano il numero di righe trovate e il
  numero di record validi dopo i filtri.

- **Dopo la normalizzazione:** abbiamo aperto i CSV in VS Code e controllato
  a campione che i dati fossero coerenti (date, tipi, allegati).

- **Dopo il caricamento MySQL:** abbiamo eseguito query per
  verificare che il numero di record corrispondesse a quello del tracciato.

- **Sui filtri della Fonte 2:** abbiamo verificato manualmente che tutte le
  date fossero ≥ 12/04/2024 e che tutti i tipi contenessero "Delibere".

- **Sugli allegati:** abbiamo controllato che i percorsi nel CSV puntassero
  a file effettivamente esistenti nelle cartelle `allegati/`.

Tutto è risultato coerente e corretto.

---

## Riusabilità

L'intero progetto è stato pensato per essere riutilizzabile in contesti simili:

- La classe `BaseScraper` può essere estesa per nuovi portali.
- Il file `config/sources.yaml` separa i parametri variabili (URL, selettori)
  dal codice Python.
- Le tre fasi (E, T, L) sono indipendenti: si può modificare una senza
  impattare le altre.
- Il tracciato di mezzo è un contratto stabile: aggiungere una terza fonte
  significa solo aggiornare l'estrazione e la normalizzazione.

---
## Istruzioni per l'esecuzione

### 1. Installare le dipendenze
```bash
pip install -r requirements.txt
```

### 2. Eseguire la pipeline (Singolo comando)
Grazie agli orchestratori introdotti nella cartella [`skills/`](skills/), non è più necessario eseguire manualmente i singoli script di estrazione, normalizzazione e caricamento. 

È possibile lanciare l'intera pipeline (Estrai → Normalizza → Carica) con un unico comando:

**Per portali statici**
```bash
python skills/run_static.py --config config/sources.yaml
```

**Per portali dinamici**
```bash
python skills/run_dynamic.py --config config/sources.yaml
```

Per i dettagli su come creare nuove configurazioni YAML usando i template e per tutte le opzioni avanzate disponibili, consulta la guida dedicata in [`skills/README.md`](skills/README.md).

---

*Progetto realizzato da Mattia il 29 maggio 2026.*
