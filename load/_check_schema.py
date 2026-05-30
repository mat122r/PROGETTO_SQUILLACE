import mysql.connector

conn = mysql.connector.connect(host='localhost', port=3306, user='root', password='', database='intermedimc.sql')
cur = conn.cursor()
for t in ['mcputerecupubbinte', 'mcrecorecuallepubb', 'mcreterecuanag']:
    cur.execute(f'SHOW CREATE TABLE `{t}`')
    row = cur.fetchone()
    print(f'\n=== {t} ===')
    print(row[1])
cur.close(); conn.close()
