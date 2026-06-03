# SKILL – ETL Pipeline per Portali Comunali

## Identità di questa skill

Sono una skill che permette di aggiungere nuovi portali comunali alla pipeline
ETL esistente e di eseguire l'estrazione, la normalizzazione e il caricamento
dei dati su MySQL. Posso operare in modalità completa o incrementale.

---

## Trigger di attivazione

Frasi che attivano questa skill:
- "aggiungi il comune di X"
- "scarica i dati dal portale Y"
- "configura una nuova fonte"
- "esegui la pipeline per Z"
- "estrai i dati da [URL]"
- "aggiorna il database con nuovi atti"

---

## Strumenti disponibili

| Strumento       | Quando usarlo                        | Comando                                                        |
|-----------------|--------------------------------------|----------------------------------------------------------------|
| `run_static.py`  | Portale HTML statico (BeautifulSoup) | `python skills/run_static.py --config config/portale.yaml`    |
| `run_dynamic.py` | Portale JS dinamico (Selenium)       | `python skills/run_dynamic.py --config config/portale.yaml`   |

Entrambi supportano i flag:

| Flag              | Effetto                                                          |
|-------------------|------------------------------------------------------------------|
| `--config`        | **(obbligatorio)** Percorso del file YAML di configurazione      |
| `--incremental`   | Elabora solo i nuovi atti non ancora processati                  |
| `--no-normalize`  | Salta la fase di normalizzazione                                 |
| `--no-load`       | Salta il caricamento su MySQL                                    |
| `--db-host`       | Sovrascrive l'host MySQL                                         |
| `--db-user`       | Sovrascrive l'utente MySQL                                       |
| `--db-password`   | Sovrascrive la password MySQL                                    |
| `--db-name`       | Sovrascrive il nome del database MySQL                           |

---

## Workflow obbligatorio (step-by-step)

1. **Determina il tipo di portale**: statico o dinamico (vedi guida sotto).
2. **Copia il template YAML** appropriato da `skills/` a `config/`.
3. **Compila il file YAML** con i selettori CSS del nuovo portale.
4. **Esegui l'orchestratore** con il flag `--config`.
5. **Verifica il riepilogo finale** nei log.
6. Per esecuzioni successive, usa `--incremental` per estrarre solo nuovi atti.

---

## Regole vincolanti (MUST)

- **NON** generare mai un nuovo scraper Python da zero.
- **NON** modificare i file in `scrapers/`.
- **USARE SEMPRE** un file YAML in `config/` come configurazione.
- **SALVARE** le nuove configurazioni in `config/`, mai in `skills/`.
- Per aggiornamenti periodici, usare `--incremental`.

---

## Come determinare se un portale è statico o dinamico

1. Apri il portale nel browser.
2. Disabilita JavaScript (DevTools → Settings → Debugger → "Disable JavaScript").
3. Ricarica la pagina.
4. Se la tabella degli atti **scompare o è vuota** → **portale dinamico** → usa `run_dynamic.py`.
5. Se la tabella è **ancora visibile e popolata** → **portale statico** → usa `run_static.py`.

---

## Modalità incrementale

Gli orchestratori supportano il flag `--incremental`. Quando attivo:

- Legge il file `.last_run_static.json` o `.last_run_dynamic.json` in `data/`
  per sapere quali atti sono già stati processati (identificati da una chiave univoca).
- Elabora **solo i nuovi atti**, saltando quelli già presenti.
- Aggiorna automaticamente il file di stato al termine dell'esecuzione.

**Chiavi univoche utilizzate:**
- Portali statici: `numero_reg||data_atto`
- Portali dinamici: `numero_atto||data_atto`

---

## Esempio operativo completo

**Scenario:** L'utente chiede "aggiungi il comune di Borgia".

```bash
# 1. Analizzo il portale e determino che è statico

# 2. Copio il template nella cartella config/
copy skills\template_static.yaml config\borgia.yaml

# 3. Compilo i selettori CSS nel file YAML (con F12 sul browser)
#    → name, base_url, list_url, table_selector, row_selector, fields, ...

# 4. Prima esecuzione completa
python skills/run_static.py --config config/borgia.yaml

# Output atteso:
# Atti inseriti:       150
# Documenti inseriti:  320
# Pipeline completata con successo. ✓

# 5. Aggiornamenti periodici (solo nuovi atti)
python skills/run_static.py --config config/borgia.yaml --incremental
# Output atteso (se ci sono 3 nuovi atti):
# Nuovi record da processare: 3
# Atti inseriti:       3
# Pipeline completata con successo. ✓
```

---

## File generati dalla pipeline

| File                          | Descrizione                                      |
|-------------------------------|--------------------------------------------------|
| `data/fonte1_raw.csv`         | CSV grezzo estratto dallo scraper statico        |
| `data/fonte2_raw.csv`         | CSV grezzo estratto dallo scraper dinamico       |
| `data/tracciato_mezzo.csv`    | CSV normalizzato (tracciato di mezzo unificato)  |
| `data/.last_run_static.json`  | File di stato per la modalità incrementale       |
| `data/.last_run_dynamic.json` | File di stato per la modalità incrementale       |
| `allegati/fonte1/<N.Reg>/`    | PDF scaricati dal portale statico                |
| `allegati/fonte2/<N.Atto>/`   | PDF scaricati dal portale dinamico               |

---

*Skill creata il 3 giugno 2026 – Progetto Squillace ETL.*
