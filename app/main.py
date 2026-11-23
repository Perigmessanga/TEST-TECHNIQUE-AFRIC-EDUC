import hashlib
import hmac
import os
import secrets
import sqlite3
import time
import json
import httpx
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

BASE = Path(__file__).resolve().parent.parent
DB_PATH = BASE / "passage.db"
APP_SECRET = os.getenv("APP_SECRET", "dev-only-change-in-production")
SESSION_SECONDS = int(os.getenv("SESSION_SECONDS", "3600"))
AI_MONTHLY_LIMIT = float(os.getenv("AI_MONTHLY_LIMIT", "1.00"))

app = FastAPI(title="Passage — Afric'Éduc")
app.mount("/static", StaticFiles(directory=str(BASE / "static")), name="static")


def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
    finally:
        conn.close()


def utcnow():
    return datetime.now(timezone.utc)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, login TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, role TEXT NOT NULL, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS students(id INTEGER PRIMARY KEY, name TEXT NOT NULL, class_name TEXT NOT NULL, establishment TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'actif');
    CREATE TABLE IF NOT EXISTS parent_students(parent_id INTEGER NOT NULL, student_id INTEGER NOT NULL, PRIMARY KEY(parent_id, student_id));
    CREATE TABLE IF NOT EXISTS badges(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL UNIQUE, serial TEXT NOT NULL UNIQUE, signing_secret TEXT NOT NULL, state TEXT NOT NULL, issued_at TEXT NOT NULL, replaced_by INTEGER);
    CREATE TABLE IF NOT EXISTS control_points(id INTEGER PRIMARY KEY, establishment TEXT NOT NULL, label TEXT NOT NULL, type TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS routes(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, point_id INTEGER NOT NULL, sequence INTEGER NOT NULL, start_time TEXT NOT NULL, end_time TEXT NOT NULL, days TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS exceptions(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, date TEXT NOT NULL, kind TEXT NOT NULL, approved_by INTEGER);
    CREATE TABLE IF NOT EXISTS passages(id INTEGER PRIMARY KEY, badge_id INTEGER NOT NULL, point_id INTEGER NOT NULL, local_time TEXT NOT NULL, server_time TEXT NOT NULL, device_id TEXT NOT NULL, local_event_id TEXT UNIQUE NOT NULL, nonce TEXT UNIQUE NOT NULL, state TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS anomalies(id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL, type TEXT NOT NULL, date TEXT NOT NULL, passage_id INTEGER, state TEXT NOT NULL DEFAULT 'nouvelle');
    CREATE TABLE IF NOT EXISTS outgoing_messages(id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL, anomaly_id INTEGER NOT NULL, text TEXT NOT NULL, state TEXT NOT NULL, reason TEXT, created_at TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS summaries(id INTEGER PRIMARY KEY, class_name TEXT NOT NULL, date TEXT NOT NULL, counts_json TEXT NOT NULL, text TEXT NOT NULL, origin TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS ai_calls(id INTEGER PRIMARY KEY, at TEXT NOT NULL, model TEXT NOT NULL, input_tokens INTEGER NOT NULL, output_tokens INTEGER NOT NULL, cost REAL NOT NULL, status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, actor TEXT, action TEXT NOT NULL, details TEXT);
    """)
    conn.commit(); conn.close()

init_db()


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Minimum 8 caractères")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        _, salt, digest = encoded.split("$", 2)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 200_000).hex()
        return hmac.compare_digest(digest, candidate)
    except Exception:
        return False

SESSIONS: dict[str, dict] = {}
LOGIN_ATTEMPTS: dict[str, list[float]] = {}


def auth(request: Request):
    token = request.cookies.get("session")
    session = SESSIONS.get(token or "")
    if not session or session["expires"] < time.time():
        raise HTTPException(status_code=401, detail="Session requise")
    return session


def require_role(*roles):
    def guard(request: Request):
        session = auth(request)
        if session["role"] not in roles:
            raise HTTPException(status_code=403, detail="Accès refusé")
        return session
    return guard


class Login(BaseModel):
    login: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)

@app.post("/api/login")
def login(payload: Login, request: Request, conn=Depends(db)):
    key = request.client.host if request.client else "unknown"
    recent = [v for v in LOGIN_ATTEMPTS.get(key, []) if v > time.time() - 300]
    if len(recent) >= 5:
        raise HTTPException(status_code=429, detail="Identifiants invalides")
    row = conn.execute("SELECT * FROM users WHERE login=?", (payload.login.strip(),)).fetchone()
    valid = row is not None and verify_password(payload.password, row["password_hash"])
    if not valid:
        recent.append(time.time()); LOGIN_ATTEMPTS[key] = recent
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    LOGIN_ATTEMPTS.pop(key, None)
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {"user_id": row["id"], "role": row["role"], "expires": time.time() + SESSION_SECONDS}
    response = JSONResponse({"ok": True, "role": row["role"]})
    response.set_cookie("session", token, httponly=True, samesite="lax", max_age=SESSION_SECONDS)
    return response

@app.post("/api/logout")
def logout(request: Request):
    SESSIONS.pop(request.cookies.get("session", ""), None)
    response = JSONResponse({"ok": True}); response.delete_cookie("session"); return response


class Student(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    class_name: str = Field(min_length=1, max_length=30)
    establishment: str = Field(min_length=1, max_length=100)

@app.post("/api/students")
def create_student(payload: Student, session=Depends(require_role("responsable")), conn=Depends(db)):
    cur = conn.execute("INSERT INTO students(name,class_name,establishment,state) VALUES(?,?,?,?)", (payload.name, payload.class_name, payload.establishment, "actif"))
    student_id = cur.lastrowid
    serial = secrets.token_urlsafe(18)
    signing_secret = secrets.token_hex(32)
    conn.execute("INSERT INTO badges(student_id,serial,signing_secret,state,issued_at) VALUES(?,?,?,?,?)", (student_id, serial, signing_secret, "actif", utcnow().isoformat()))
    conn.commit()
    return {"id": student_id, "badge_serial": serial}

@app.post("/api/badges/{student_id}/token")
def badge_token(student_id: int, session=Depends(require_role("responsable", "agent")), conn=Depends(db)):
    badge = conn.execute("SELECT * FROM badges WHERE student_id=? AND state='actif'", (student_id,)).fetchone()
    if not badge:
        raise HTTPException(404, "Badge actif introuvable")
    nonce = secrets.token_urlsafe(16)
    expires = int(time.time()) + 30
    payload = f"{badge['serial']}.{expires}.{nonce}".encode()
    sig = hmac.new(badge["signing_secret"].encode(), payload, hashlib.sha256).hexdigest()[:16]
    return {"token": payload.decode() + "." + sig, "expires_at": expires}


class SyncItem(BaseModel):
    point_id: int = Field(gt=0)
    local_time: str = Field(min_length=10, max_length=40)
    device_id: str = Field(min_length=1, max_length=100)
    badge_token: str = Field(min_length=20, max_length=300)
    local_event_id: str = Field(min_length=16, max_length=100)

class SyncBatch(BaseModel):
    items: list[SyncItem] = Field(min_length=1, max_length=100)

@app.post("/api/sync")
def sync(batch: SyncBatch, session=Depends(require_role("agent", "responsable")), conn=Depends(db)):
    accepted = duplicates = 0
    rejected = []
    for item in batch.items:
        existing = conn.execute("SELECT id FROM passages WHERE local_event_id=?", (item.local_event_id,)).fetchone()
        if existing:
            duplicates += 1
            continue
        try:
            serial, expires_s, nonce, sig = item.badge_token.split(".")
            badge = conn.execute("SELECT * FROM badges WHERE serial=? AND state='actif'", (serial,)).fetchone()
            if not badge:
                rejected.append({"event": item.local_event_id, "reason": "badge_invalide"}); continue
            payload = f"{serial}.{expires_s}.{nonce}".encode()
            expected = hmac.new(badge["signing_secret"].encode(), payload, hashlib.sha256).hexdigest()[:16]
            if int(expires_s) < int(time.time()) or not hmac.compare_digest(expected, sig):
                rejected.append({"event": item.local_event_id, "reason": "badge_expire_ou_invalide"}); continue
            used = conn.execute("SELECT id FROM passages WHERE nonce=?", (nonce,)).fetchone()
            if used:
                rejected.append({"event": item.local_event_id, "reason": "badge_deja_utilise"}); continue
            local_dt = datetime.fromisoformat(item.local_time.replace("Z", "+00:00"))
            if abs((utcnow() - local_dt.astimezone(timezone.utc)).total_seconds()) > 3600:
                rejected.append({"event": item.local_event_id, "reason": "heure_locale_invalide"}); continue
            point = conn.execute("SELECT id FROM control_points WHERE id=?", (item.point_id,)).fetchone()
            if not point:
                rejected.append({"event": item.local_event_id, "reason": "point_inconnu"}); continue
        except (ValueError, AttributeError):
            rejected.append({"event": item.local_event_id, "reason": "format_invalide"}); continue
        cur = conn.execute("INSERT INTO passages(badge_id,point_id,local_time,server_time,device_id,local_event_id,nonce,state) VALUES(?,?,?,?,?,?,?,?)", (badge["id"], item.point_id, item.local_time, utcnow().isoformat(), item.device_id, item.local_event_id, nonce, "synchronisé"))
        conn.commit(); accepted += 1
        detect_duplicate(badge["id"], cur.lastrowid, conn)
    return {"accepted": accepted, "duplicates": duplicates, "rejected": rejected}


def detect_duplicate(badge_id: int, passage_id: int, conn):
    rows = conn.execute("SELECT * FROM passages WHERE badge_id=? ORDER BY server_time DESC LIMIT 2", (badge_id,)).fetchall()
    if len(rows) == 2:
        a = datetime.fromisoformat(rows[0]["server_time"])
        b = datetime.fromisoformat(rows[1]["server_time"])
        if abs((a-b).total_seconds()) < 60:
            student = conn.execute("SELECT student_id FROM badges WHERE id=?", (badge_id,)).fetchone()
            existing = conn.execute("SELECT id FROM anomalies WHERE student_id=? AND type='double_scan' AND passage_id=?", (student["student_id"], passage_id)).fetchone()
            if not existing:
                conn.execute("INSERT INTO anomalies(student_id,type,date,passage_id,state) VALUES(?,?,?,?,?)", (student["student_id"], "double_scan", utcnow().date().isoformat(), passage_id, "nouvelle")); conn.commit()


@app.get("/api/students/{student_id}")
def student_detail(student_id: int, session=Depends(auth), conn=Depends(db)):
    if session["role"] == "parent":
        allowed = conn.execute("SELECT 1 FROM parent_students WHERE parent_id=? AND student_id=?", (session["user_id"], student_id)).fetchone()
        if not allowed:
            raise HTTPException(403, "Accès refusé")
    row = conn.execute("SELECT * FROM students WHERE id=?", (student_id,)).fetchone()
    if not row:
        raise HTTPException(404, "Élève introuvable")
    return dict(row)

@app.get("/", response_class=HTMLResponse)
def index():
    return """<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'><title>Passage</title><link rel='stylesheet' href='/static/app.css'><main><h1>Passage</h1><form id='login'><input name='login' placeholder='Identifiant' required><input name='password' type='password' minlength='8' required><button>Connexion</button></form><pre id='out'></pre></main><script src='/static/app.js'></script>"""


class SummaryRequest(BaseModel):
    class_name: str = Field(min_length=1, max_length=30)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")


@app.post("/api/summaries")
def create_summary(payload: SummaryRequest, session=Depends(require_role("responsable")), conn=Depends(db)):
    existing = conn.execute("SELECT * FROM summaries WHERE class_name=? AND date=?", (payload.class_name, payload.date)).fetchone()
    if existing:
        return dict(existing)

    students = conn.execute("SELECT id FROM students WHERE class_name=?", (payload.class_name,)).fetchall()
    ids = [row["id"] for row in students]
    present = 0
    retards = 0
    outside = 0
    for student_id in ids:
        rows = conn.execute("SELECT * FROM passages p JOIN badges b ON b.id=p.badge_id WHERE b.student_id=? AND p.server_time LIKE ?", (student_id, payload.date + "%")).fetchall()
        if rows:
            present += 1
        retards += sum(1 for row in rows if "retard" in row["state"])
        outside += sum(1 for row in rows if "hors" in row["state"])
    counts = {"eleves": len(ids), "present": present, "retards": retards, "sorties_hors_plage": outside}

    if os.getenv("AI_API_KEY"):
        monthly_cost = conn.execute("SELECT COALESCE(SUM(cost),0) AS total FROM ai_calls WHERE at>=?", ((utcnow().replace(day=1)).isoformat(),)).fetchone()["total"]
        if monthly_cost >= AI_MONTHLY_LIMIT:
            text = fallback_summary(counts)
            origin = "plafond"
        else:
            prompt = "À partir uniquement de ce JSON, rédige une phrase française concise. Ne calcule rien: " + json.dumps(counts, ensure_ascii=False)
            try:
                response = httpx.post(os.getenv("AI_BASE_URL", "https://api.openai.com/v1/chat/completions"), headers={"Authorization": "Bearer " + os.getenv("AI_API_KEY", "")}, json={"model": os.getenv("AI_MODEL", "gpt-4o-mini"), "messages": [{"role":"user","content":prompt}], "temperature":0}, timeout=8)
                response.raise_for_status()
                data = response.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                cost = (input_tokens * 0.00000015) + (output_tokens * 0.00000060)
                conn.execute("INSERT INTO ai_calls(at,model,input_tokens,output_tokens,cost,status) VALUES(?,?,?,?,?,?)", (utcnow().isoformat(), os.getenv("AI_MODEL", "gpt-4o-mini"), input_tokens, output_tokens, cost, "succès")); conn.commit()
                if not validate_summary(text, counts):
                    raise ValueError("Synthèse contenant des chiffres non fiables")
                origin = "modele"
            except Exception:
                conn.execute("INSERT INTO ai_calls(at,model,input_tokens,output_tokens,cost,status) VALUES(?,?,?,?,?,?)", (utcnow().isoformat(), os.getenv("AI_MODEL", "gpt-4o-mini"), 0, 0, 0, "repli")); conn.commit()
                text = fallback_summary(counts); origin = "gabarit"
    else:
        text = fallback_summary(counts); origin = "gabarit"
    conn.execute("INSERT INTO summaries(class_name,date,counts_json,text,origin) VALUES(?,?,?,?,?)", (payload.class_name, payload.date, json.dumps(counts), text, origin)); conn.commit()
    row = conn.execute("SELECT * FROM summaries WHERE class_name=? AND date=?", (payload.class_name, payload.date)).fetchone()
    return dict(row)


def fallback_summary(counts):
    return f"{counts['eleves']} élèves, {counts['present']} présents, {counts['retards']} retards au portail, {counts['sorties_hors_plage']} sorties hors plage."


def validate_summary(text: str, counts: dict) -> bool:
    # Un modèle ne peut utiliser que les chiffres fournis par la base.
    if any(char.isdigit() for char in text):
        return all(str(value) in text for value in counts.values())
    return True


@app.post("/api/anomalies/detect")
def detect_missed_windows(session=Depends(require_role("responsable")), conn=Depends(db)):
    today = utcnow().date().isoformat()
    count = 0
    for route in conn.execute("SELECT * FROM routes WHERE end_time <= ?", (utcnow().strftime("%H:%M"),)).fetchall():
        exception = conn.execute("SELECT 1 FROM exceptions WHERE student_id=? AND date=?", (route["student_id"], today)).fetchone()
        if exception:
            continue
        passage = conn.execute("SELECT 1 FROM passages p JOIN badges b ON b.id=p.badge_id WHERE b.student_id=? AND p.point_id=? AND p.server_time LIKE ?", (route["student_id"], route["point_id"], today + "%")).fetchone()
        if not passage:
            exists = conn.execute("SELECT 1 FROM anomalies WHERE student_id=? AND type='absence_attendue' AND date=?", (route["student_id"], today)).fetchone()
            if not exists:
                conn.execute("INSERT INTO anomalies(student_id,type,date,state) VALUES(?,?,?,?)", (route["student_id"], "absence_attendue", today, "nouvelle")); count += 1
    conn.commit()
    return {"created": count}


@app.get("/api/anomalies")
def list_anomalies(session=Depends(auth), conn=Depends(db)):
    if session["role"] == "parent":
        rows = conn.execute("SELECT a.* FROM anomalies a JOIN parent_students ps ON ps.student_id=a.student_id WHERE ps.parent_id=?", (session["user_id"],)).fetchall()
    elif session["role"] == "responsable":
        rows = conn.execute("SELECT * FROM anomalies").fetchall()
    else:
        raise HTTPException(403, "Agent: accès aux anomalies interdit")
    return [dict(row) for row in rows]
