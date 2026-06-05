import sys
from pathlib import Path

# Aggiungi ROOT al path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import yaml
from transform.normalizza import normalizza
from load.carica_mysql import carica

print("="*60)
print(" Eseguendo FASE 2: Normalizzazione")
print("="*60)
f1 = ROOT / "data" / "fonte1_raw.csv"
f2 = ROOT / "data" / "fonte2_raw.csv"

tracciato = normalizza(csv_fonte1=f1, csv_fonte2=f2)

print("="*60)
print(" Eseguendo FASE 3: Caricamento MySQL")
print("="*60)

with open(ROOT / "config" / "sources.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

db_config = config.get("database", {})
res = carica(
    tracciato_csv=tracciato,
    host=db_config.get("host"),
    user=db_config.get("user"),
    password=db_config.get("password"),
    database=db_config.get("database"),
    truncate=True
)

print(f"Risultati Finali: {res}")
