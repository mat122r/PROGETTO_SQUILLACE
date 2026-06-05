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

##  Strumenti disponibili


| Strumento         | Quando usarlo                          | Comando                                      |
|-------------------|----------------------------------------|----------------------------------------------|
| run_pipeline.py   | MASTER: Esegue tutta la pipeline ETL   | python skills/run_pipeline.py [--truncate \| --append] |
| run_static.py     | Sotto-modulo per un solo portale HTML  | python skills/run_static.py --config ...     |
| run_dynamic.py    | Sotto-modulo per un solo portale JS    | python skills/run_dynamic.py --config ...    |

##  Workflow obbligatorio per l'Agente (Step-by-Step)
1. **Identifica la fonte**: Determina se il nuovo comune è statico o dinamico.
2. **Aggiorna la configurazione**: Inserisci i selettori CSS del nuovo comune direttamente dentro `config/sources.yaml`.
3. **Esegui in un colpo solo**: Lancia the Master Orchestrator `python skills/run_pipeline.py`.
4. **Mantenimento**: Usa `python skills/run_pipeline.py --incremental` per aggiornamenti periodici.

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
4. Se la tabella degli atti **scompare o è vuota** → **portale dinamico** → imposta `tipo: "dynamic"` nel YAML.
5. Se la tabella è **ancora visibile e popolata** → **portale statico** → imposta `tipo: "static"` nel YAML.

---

## Modalità incrementale

Gli orchestratori supportano il flag `--incremental`. Quando attivo:

- Legge il file `.last_run_static.json` o `.last_run_dynamic.json` in `data/`
  per sapere quali atti sono già stati processati (identificati da una chiave univoca).
- Elabora **solo i nuovi atti**, saltando quelli già presenti.
- Aggiorna automaticamente il file di stato al termine dell'esecuzione.

**Chiavi univoche utilizzate:**
- Portali statici: `numero_reg`
- Portali dinamici: `numero_atto||data_atto`

---

## Esempio operativo completo

**Scenario:** L'utente chiede "aggiungi il comune di Borgia".

```yaml
# 1. Apro config/sources.yaml e aggiungo la nuova sezione in fondo

fonte3:
  tipo: "static"                        # statico: tabella visibile senza JavaScript
  name: "Comune di Borgia – Albo Pretorio"
  base_url: "https://albo.comune.borgia.cz.it"
  list_url: "/archivio/cerca.php"
  table_selector: "table.tablesorter"   # trovato con F12 sul browser
  row_selector: "tbody tr"
  fields:
    numero_reg:         "td:nth-child(1)"
    tipo:               "td:nth-child(2)"
    oggetto:            "td:nth-child(4)"
    data_pubblicazione: "td:nth-child(5)"
    data_scadenza:      "td:nth-child(6)"
    link_dettaglio:     "td:nth-child(7) a"
```

```bash
# 2. Lancio il Master Orchestrator — gestisce tutto in automatico
python skills/run_pipeline.py

# Output atteso:
#   Fonti configurate: 3
#     - fonte1: ASMENET Squillace [static]
#     - fonte2: Halley Squillace [dynamic]
#     - fonte3: Comune di Borgia [static]      ← rilevato automaticamente
#
# [1/3] Avvio pipeline ASMENET Squillace...
#   [OK] ASMENET Squillace completata.
# [2/3] Avvio pipeline Halley Squillace...
#   [OK] Halley Squillace completata.
# [3/3] Avvio pipeline Comune di Borgia...
#   [OK] Comune di Borgia completata.
#
# PIPELINE ETL GLOBALE TERMINATA – 3/3 fonti elaborate. [OK]

# 3. Aggiornamenti periodici (solo nuovi atti per tutti i comuni)
python skills/run_pipeline.py --incremental
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

*Progetto personale – Pipeline ETL | Mattia Cannavò | Terminato il 29 maggio 2026, revisionato il 5 giugno 2026*
