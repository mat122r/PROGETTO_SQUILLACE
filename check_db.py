import mysql.connector
import yaml

try:
    with open('config/sources.yaml', 'r') as f:
        cfg = yaml.safe_load(f)
    db = cfg['database']
    conn = mysql.connector.connect(
        host=db.get('host', 'localhost'),
        port=db.get('port', 3306),
        user=db.get('user', 'root'),
        password=db.get('password', '')
    )
    cur = conn.cursor()
    cur.execute("USE intermedimc;")
    cur.execute("SELECT COUNT(*) FROM mcputerecupubbinte;")
    print("ATTI:", cur.fetchone()[0])
    cur.execute("SELECT COUNT(*) FROM mcrecorecuallepubb;")
    print("ALLEGATI:", cur.fetchone()[0])
    conn.close()
except Exception as e:
    print(e)
