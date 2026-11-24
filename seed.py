import sqlite3
import secrets
from app.main import hash_password, DB_PATH

conn = sqlite3.connect(DB_PATH)
conn.execute("DELETE FROM parent_students"); conn.execute("DELETE FROM badges"); conn.execute("DELETE FROM students"); conn.execute("DELETE FROM users"); conn.execute("DELETE FROM control_points"); conn.execute("DELETE FROM routes"); conn.execute("DELETE FROM passages"); conn.execute("DELETE FROM anomalies"); conn.execute("DELETE FROM outgoing_messages"); conn.execute("DELETE FROM summaries"); conn.execute("DELETE FROM ai_calls")
users = [
    ("Responsable","responsable","responsable"),
    ("Agent","agent","agent"),
    ("Parent A","parent1","parent"),
    ("Parent B","parent2","parent")]
for i,(name,login,role) in enumerate(users,1):
    conn.execute("INSERT OR IGNORE INTO users(id,name,login,password_hash,role,created_at) VALUES(?,?,?,?,?,datetime('now'))", (i,name,login,hash_password("Test1234"),role))
conn.execute("INSERT INTO control_points(id,establishment,label,type) VALUES(1,'École Afric','Portail entrée','portail')")
conn.execute("INSERT INTO control_points(id,establishment,label,type) VALUES(2,'École Afric','Portail sortie','portail')")
for i in range(1,6):
    conn.execute("INSERT INTO students(id,name,class_name,establishment,state) VALUES(?,?,?,?,?)",(i,f"Élève {i}","6eA","École Afric","actif"))
    serial=secrets.token_urlsafe(18); secret=secrets.token_hex(32)
    conn.execute("INSERT INTO badges(id,student_id,serial,signing_secret,state,issued_at) VALUES(?,?,?,?,?,datetime('now'))",(i,i,serial,secret,"actif"))
    for point in (1,2):
        conn.execute("INSERT INTO routes(student_id,point_id,sequence,start_time,end_time,days) VALUES(?,?,?,?,?,?)",(i,point,point,'07:00','07:45','LMMJV') if point==1 else (i,point,point,'15:30','16:15','LMMJV'))
conn.execute("INSERT INTO parent_students VALUES(3,1)"); conn.execute("INSERT INTO parent_students VALUES(3,2)"); conn.execute("INSERT INTO parent_students VALUES(4,3)")
conn.commit(); conn.close()
print("Base initialisée. Comptes: responsable / agent / parent1 / parent2 — mot de passe: Test1234")
