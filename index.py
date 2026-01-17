import os
import sys
import threading
import subprocess
import zipfile
import random
import hashlib
from datetime import datetime, timedelta
import sqlite3
from flask import Flask, request, redirect, session, url_for, render_template_string
import telebot

# ---------------- CONFIG ----------------
PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = "data"
BOTS_DIR = os.path.join(DATA_DIR, "bots")
DB_FILE = os.path.join(DATA_DIR, "panel.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BOTS_DIR, exist_ok=True)

# Render ENV variables ONLY (no input)
BOT_TOKEN = os.environ.get("PANEL_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("PANEL_ADMIN_ID"))

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("Missing PANEL_BOT_TOKEN or PANEL_ADMIN_ID")

# ---------------- DATABASE ----------------
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, password TEXT, verified INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS uploads (telegram_id INTEGER, bot_name TEXT, file_size INTEGER, upload_time TEXT)")
conn.commit()

# ---------------- TELEGRAM BOT ----------------
tg = telebot.TeleBot(BOT_TOKEN)
OTP_CACHE = {}
APPROVE_CACHE = {}
RUNNING_BOTS = {}

def send_otp(tg_id):
    otp = str(random.randint(100000, 999999))
    OTP_CACHE[tg_id] = otp
    try:
        tg.send_message(
            tg_id,
            f"🛡️ *KAALIX SECURITY*\n\nYour Login OTP: `{otp}`\n\nDo not share this code.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("OTP send error:", e)

@tg.message_handler(commands=["start"])
def tg_start(msg):
    tg.reply_to(msg, "🚀 KAALIX Premium Panel Bot is Online.")

@tg.message_handler(commands=["approve"])
def tg_approve(msg):
    APPROVE_CACHE[msg.from_user.id] = True
    tg.reply_to(msg, "✅ Access Approved! You can now use the dashboard.")

def telegram_polling():
    tg.infinity_polling(skip_pending=True)

# ---------------- FLASK APP ----------------
app = Flask(__name__)
app.secret_key = "kaalix_secret_key_123"
app.permanent_session_lifetime = timedelta(days=7)

# ---- UI (UNCHANGED) ----
BASE_HEAD = """<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
body { font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; }
.glass { background: rgba(30,41,59,.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,.1); }
</style>
"""

# (LOGIN_HTML, OTP_HTML, DASH_HTML, EDIT_HTML exactly same as your original)
# 👉 UI code intentionally untouched for safety
# 👉 For brevity not repeating here, logic below unchanged

# ---------------- ROUTES ----------------

@app.route("/", methods=["GET","POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        try:
            tgid = int(request.form["tgid"])
            password = request.form["password"]
            hp = hashlib.sha256(password.encode()).hexdigest()

            cur.execute("SELECT password, verified FROM users WHERE telegram_id=?", (tgid,))
            row = cur.fetchone()

            if not row:
                send_otp(tgid)
                cur.execute("INSERT INTO users VALUES (?,?,0)", (tgid, hp))
                conn.commit()
                session["pending"] = tgid
                return redirect(url_for("otp"))

            if row[0] == hp and row[1] == 1:
                session["user"] = tgid
                return redirect(url_for("dashboard"))
        except:
            pass

    return render_template_string(LOGIN_HTML)

@app.route("/otp", methods=["GET","POST"])
def otp():
    if "pending" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        tgid = session["pending"]
        if OTP_CACHE.get(tgid) == request.form.get("otp"):
            cur.execute("UPDATE users SET verified=1 WHERE telegram_id=?", (tgid,))
            conn.commit()
            session.pop("pending")
            session["user"] = tgid
            return redirect(url_for("dashboard"))

    return render_template_string(OTP_HTML)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    uid = session["user"]
    if not APPROVE_CACHE.get(uid):
        return "Approval required. Use /approve in Telegram."

    bots = {}
    for f in os.listdir(BOTS_DIR):
        if f.startswith(str(uid) + "_"):
            bots[f] = "RUNNING" if f in RUNNING_BOTS else "STOPPED"

    return render_template_string(DASH_HTML, bots=bots, uid=uid)

@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session:
        return redirect(url_for("login"))

    uid = session["user"]
    file = request.files.get("botfile")
    if not file:
        return "No file"

    file.seek(0,2)
    size = file.tell()
    file.seek(0)
    if size > 1024 * 1024:
        return "File too large"

    filename = f"{uid}_{file.filename}"
    path = os.path.join(BOTS_DIR, filename)
    file.save(path)

    if filename.endswith(".zip"):
        with zipfile.ZipFile(path) as z:
            z.extractall(BOTS_DIR)
        os.remove(path)

    cur.execute("INSERT INTO uploads VALUES (?,?,?,?)",
                (uid, filename, size, datetime.now().isoformat()))
    conn.commit()
    return redirect(url_for("dashboard"))

@app.route("/startbot/<bot>")
def startbot(bot):
    path = os.path.join(BOTS_DIR, bot)
    if bot not in RUNNING_BOTS:
        p = subprocess.Popen([sys.executable, path])
        RUNNING_BOTS[bot] = p
    return redirect(url_for("dashboard"))

@app.route("/stopbot/<bot>")
def stopbot(bot):
    p = RUNNING_BOTS.get(bot)
    if p:
        try:
            p.terminate()
        except:
            pass
        RUNNING_BOTS.pop(bot, None)
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- START ----------------
if __name__ == "__main__":
    threading.Thread(target=telegram_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
