import mysql.connector

for db_name in ['intermediMC', 'intermedimc', 'intermedimc.sql', 'intermediMC.sql']:
    try:
        conn = mysql.connector.connect(host='localhost', port=3306, user='root', password='', database=db_name)
        cur = conn.cursor()
        cur.execute('SHOW TABLES')
        tables = [r[0] for r in cur.fetchall()]
        print(f'[OK] DB "{db_name}" -> tabelle: {tables}')
        for t in tables:
            cur.execute(f'SELECT COUNT(*) FROM `{t}`')
            print(f'   {t}: {cur.fetchone()[0]} righe')
        cur.close(); conn.close()
    except Exception as e:
        print(f'[ERR] DB "{db_name}" -> {e}')
