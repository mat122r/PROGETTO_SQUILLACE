"""
skills/run_pipeline.py
======================
Master Orchestrator globale per la pipeline ETL – Progetto Squillace.

Itera DINAMICAMENTE su tutte le fonti definite in config/sources.yaml, determinando
il tipo di orchestratore (statico o dinamico) dal campo 'tipo' di ogni fonte.
Aggiungere un nuovo comune significa solo aggiungere una sezione in sources.yaml:
zero modifiche al codice Python.

Uso:
    python skills/run_pipeline.py                  # pipeline completa tutte le fonti
    python skills/run_pipeline.py --incremental    # solo nuovi atti (delta)
    python skills/run_pipeline.py --no-load        # salta caricamento MySQL
    python skills/run_pipeline.py --check          # pre-flight check ambiente
"""

import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

# Fix encoding per terminali Windows (cp1252 non supporta caratteri Unicode)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Radice del progetto (due livelli sopra questo file: skills/ -> root)
ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# PRE-FLIGHT CHECK (--check)
# ---------------------------------------------------------------------------

def run_check():
    """Verifica l'ambiente prima di eseguire la pipeline."""
    print("=" * 60)
    print("  ETL MASTER PIPELINE – PRE-FLIGHT CHECK")
    print("=" * 60)
    errori = 0

    # 1. Versione Python
    major, minor = sys.version_info.major, sys.version_info.minor
    if major >= 3 and minor >= 9:
        print(f"  [OK] Python {major}.{minor} (>= 3.9 richiesto)")
    else:
        print(f"  [KO] Python {major}.{minor} – richiesto >= 3.9")
        errori += 1

    # 2. Dipendenze Python critiche
    dipendenze = [
        ("requests",            "requests"),
        ("bs4",                 "beautifulsoup4"),
        ("selenium",            "selenium"),
        ("pandas",              "pandas"),
        ("yaml",                "pyyaml"),
        ("mysql.connector",     "mysql-connector-python"),
        ("webdriver_manager",   "webdriver-manager"),
    ]
    for modulo, pacchetto in dipendenze:
        try:
            __import__(modulo)
            print(f"  [OK] {pacchetto}")
        except ImportError:
            print(f"  [KO] {pacchetto} non installato – esegui: pip install {pacchetto}")
            errori += 1

    # 3. Connessione MySQL
    try:
        import mysql.connector
        
        config_path = ROOT / "config" / "sources.yaml"
        db_config = {"host": "localhost", "port": 3306, "user": "root", "password": ""}
        if config_path.exists():
            with config_path.open(encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
                if isinstance(cfg, dict) and "database" in cfg:
                    db_config.update(cfg["database"])
                    
        conn = mysql.connector.connect(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 3306),
            user=db_config.get("user", "root"),
            password=db_config.get("password", "")
        )
        conn.close()
        print(f"  [OK] MySQL – connessione a {db_config.get('host')}:{db_config.get('port')} ({db_config.get('user')}) riuscita")
    except Exception as exc:
        print(f"  [KO] MySQL non raggiungibile: {exc}")
        print("       Soluzione: avviare XAMPP/MySQL, o controllare la sezione 'database' in config/sources.yaml.")
        errori += 1

    # 4. File core del workspace
    file_core = [
        ROOT / "config" / "sources.yaml",
        ROOT / "skills" / "run_static.py",
        ROOT / "skills" / "run_dynamic.py",
        ROOT / "scrapers" / "base_scraper.py",
        ROOT / "scrapers" / "fonte1_scraper.py",
        ROOT / "scrapers" / "fonte2_scraper.py",
        ROOT / "transform" / "normalizza.py",
        ROOT / "load" / "carica_mysql.py",
    ]
    for f in file_core:
        if f.exists():
            print(f"  [OK] {f.relative_to(ROOT)}")
        else:
            print(f"  [KO] File mancante: {f.relative_to(ROOT)}")
            errori += 1

    print("=" * 60)
    if errori == 0:
        print("  AMBIENTE PRONTO – nessun problema rilevato. [OK]")
        print("  Puoi lanciare: python skills/run_pipeline.py")
    else:
        print(f"  {errori} PROBLEMA/I RILEVATO/I – risolvi prima di eseguire la pipeline.")
    print("=" * 60)
    sys.exit(0 if errori == 0 else 1)


# ---------------------------------------------------------------------------
# MAIN PIPELINE
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Master Orchestrator – Pipeline ETL dinamica multi-fonte.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python skills/run_pipeline.py                 # pipeline completa
  python skills/run_pipeline.py --incremental   # solo nuovi atti (delta)
  python skills/run_pipeline.py --no-load       # senza caricamento MySQL
  python skills/run_pipeline.py --check         # verifica ambiente
        """,
    )
    parser.add_argument(
        "--incremental", action="store_true",
        help="Processa solo i nuovi atti (modalita' delta).",
    )
    parser.add_argument(
        "--no-load", action="store_true",
        help="Salta il caricamento su MySQL.",
    )
    parser.add_argument(
        "--config", default=None, metavar="PERCORSO_YAML",
        help="Percorso del file YAML di configurazione (default: config/sources.yaml).",
    )
    parser.add_argument(
        "--truncate", action="store_true",
        help="Svuota le tabelle MySQL prima del caricamento.",
    )
    parser.add_argument(
        "--append", action="store_true",
        help="Accoda ai dati esistenti in MySQL ricalcolando il progressivo.",
    )
    parser.add_argument(
        "--check", action="store_true",
        help="Esegue un pre-flight check dell'ambiente e termina.",
    )
    args = parser.parse_args()

    # Pre-flight check richiesto esplicitamente
    if args.check:
        run_check()
        return  # run_check chiama sys.exit(), ma per sicurezza

    config_file = args.config if args.config else str(ROOT / "config" / "sources.yaml")
    config_path = Path(config_file).resolve()

    modalita = "INCREMENTALE" if args.incremental else "COMPLETA"
    print("=" * 60)
    print("  ETL MASTER PIPELINE – PROGETTO SQUILLACE")
    print(f"  Modalita': {modalita}")
    print(f"  Config:   {config_path}")
    print("=" * 60)

    # 1. Lettura configurazione
    try:
        with config_path.open(encoding="utf-8") as f:
            sources_config = yaml.safe_load(f)
    except Exception as exc:
        print(f"[ERRORE] Impossibile leggere '{config_path}': {exc}")
        sys.exit(1)

    if not isinstance(sources_config, dict) or not sources_config:
        print("[ERRORE] Il file di configurazione e' vuoto o non valido.")
        sys.exit(1)

    # 2. Filtra solo le fonti valide (escludi chiavi che iniziano con "_" o simili)
    fonti = {
        nome: cfg
        for nome, cfg in sources_config.items()
        if isinstance(cfg, dict) and "name" in cfg and "tipo" in cfg
    }

    if not fonti:
        print("[ERRORE] Nessuna fonte valida trovata in sources.yaml.")
        print("         Ogni fonte deve avere almeno i campi 'name' e 'tipo'.")
        sys.exit(1)

    totale = len(fonti)
    print(f"\n  Fonti configurate: {totale}")
    for nome, cfg in fonti.items():
        print(f"    - {nome}: {cfg['name']} [{cfg['tipo']}]")

    # 3. Ambiente con encoding UTF-8 forzato (evita NativeCommandError su Windows)
    _env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    # 4. Loop dinamico su tutte le fonti (MOD 1 + MOD 5)
    
    # Cancella vecchi file filtrati
    for f in [ROOT / "data" / ".filtered_static.csv", ROOT / "data" / ".filtered_dynamic.csv"]:
        if f.exists():
            f.unlink()
            
    temp_files = []
    try:
        for indice, (nome_fonte, cfg_fonte) in enumerate(fonti.items(), start=1):
            tipo = cfg_fonte.get("tipo", "static").lower()
            nome = cfg_fonte.get("name", nome_fonte)

            tipo_label = "Portale Statico" if tipo == "static" else "Portale Dinamico"
            print(f"\n[{indice}/{totale}] Avvio pipeline {nome} ({tipo_label})...")

            # Crea file YAML temporaneo piatto per il sotto-orchestratore
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".yaml",
                dir=ROOT / "config", delete=False, prefix=f"_temp_{nome_fonte}_"
            ) as tmp:
                yaml.safe_dump(cfg_fonte, tmp, allow_unicode=True)
                temp_path = Path(tmp.name)
                temp_files.append(temp_path)

            # Seleziona il sotto-orchestratore in base al tipo
            if tipo == "static":
                script = ROOT / "skills" / "run_static.py"
            elif tipo == "dynamic":
                script = ROOT / "skills" / "run_dynamic.py"
            else:
                print(f"  [AVVISO] Tipo '{tipo}' non riconosciuto per '{nome_fonte}'. Valori validi: 'static', 'dynamic'. Fonte saltata.")
                continue

            cmd = [sys.executable, str(script), "--config", str(temp_path)]
            if args.incremental:
                cmd.append("--incremental")
            
            # I sotto-orchestratori fungono solo da estrattori
            cmd.extend(["--no-normalize", "--no-load"])

            res = subprocess.run(cmd, env=_env)

            if res.returncode != 0:
                print(f"\n  [ERRORE] Pipeline '{nome}' fallita con errore fatale (exit {res.returncode}).")
                sys.exit(res.returncode)
            else:
                print(f"\n  [OK] {nome} completata (o saltata per errore rete).")

        # 5. Normalizzazione centralizzata
        print("\n" + "=" * 60)
        print("  FASE 2 – Normalizzazione Globale")
        print("=" * 60)
        from transform.normalizza import normalizza
        
        f1 = ROOT / "data" / (".filtered_static.csv" if args.incremental else "fonte1_raw.csv")
        f2 = ROOT / "data" / (".filtered_dynamic.csv" if args.incremental else "fonte2_raw.csv")
        
        if not f1.exists() and not f2.exists():
            print("  [OK] Nessun dato da normalizzare (nessun nuovo atto trovato).")
        else:
            try:
                tracciato = normalizza(
                    csv_fonte1=f1 if f1.exists() else None,
                    csv_fonte2=f2 if f2.exists() else None
                )
                
                # 6. Caricamento centralizzato
                if not args.no_load:
                    print("\n" + "=" * 60)
                    print("  FASE 3 – Caricamento Globale su MySQL")
                    print("=" * 60)
                    from load.carica_mysql import carica
                    
                    db_config = sources_config.get("database", {})
                    carica(
                        tracciato_csv=tracciato,
                        host=db_config.get("host"),
                        user=db_config.get("user"),
                        password=db_config.get("password"),
                        database=db_config.get("database"),
                        truncate=args.truncate,
                        append=args.append
                    )
                else:
                    print("\n  [OK] Caricamento MySQL saltato (--no-load).")
            except Exception as e:
                import traceback
                traceback.print_exc()
                print(f"\n  [ERRORE FATALE] Fallimento in FASE 2 o 3: {e}")
                sys.exit(1)

        # 7. Messaggio finale
        print("\n" + "=" * 60)
        print(f"  PIPELINE ETL GLOBALE TERMINATA – {totale}/{totale} fonti elaborate. [OK]")
        print("=" * 60)

    finally:
        # Pulizia file temporanei
        for path in temp_files:
            if path.exists():
                try:
                    path.unlink()
                except Exception as exc:
                    print(f"[AVVISO] Impossibile rimuovere il file temporaneo {path.name}: {exc}")


if __name__ == "__main__":
    main()
