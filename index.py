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

# ================= CONFIG =================
PORT = int(os.environ.get("PORT", 8080))
DATA_DIR = "data"
BOTS_DIR = os.path.join(DATA_DIR, "bots")
DB_FILE = os.path.join(DATA_DIR, "panel.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BOTS_DIR, exist_ok=True)

BOT_TOKEN = os.environ.get("PANEL_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("PANEL_ADMIN_ID"))

if not BOT_TOKEN or not ADMIN_ID:
    raise RuntimeError("PANEL_BOT_TOKEN or PANEL_ADMIN_ID missing")

def is_admin(uid):
    return uid == ADMIN_ID

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    telegram_id INTEGER PRIMARY KEY,
    password TEXT,
    verified INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS uploads (
    telegram_id INTEGER,
    bot_name TEXT,
    file_size INTEGER,
    upload_time TEXT
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS approvals (
    telegram_id INTEGER PRIMARY KEY
)
""")

conn.commit()

# ================= TELEGRAM BOT =================
tg = telebot.TeleBot(BOT_TOKEN)
OTP_CACHE = {}
RUNNING_BOTS = {}

def send_otp(tg_id):
    otp = str(random.randint(100000, 999999))
    OTP_CACHE[tg_id] = otp
    tg.send_message(
        tg_id,
        f"OTP CODE: {otp}\nValid for 5 minutes.\nDo not share."
    )

@tg.message_handler(commands=["start"])
def tg_start(msg):
    tg.reply_to(msg, "KAALIX Panel Bot Online")

@tg.message_handler(commands=["approve"])
def tg_approve(msg):
    uid = msg.from_user.id
    cur.execute("INSERT OR IGNORE INTO approvals VALUES (?)", (uid,))
    conn.commit()
    tg.reply_to(msg, "✅ Approved! Now refresh the panel.")

def telegram_polling():
    tg.infinity_polling(skip_pending=True)

# ================= FLASK APP =================
app = Flask(__name__)
app.secret_key = "kaalix_secret_key"
app.permanent_session_lifetime = timedelta(days=7)

# ================= UI =================
BASE_HEAD = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<style>
body { background:#0f172a; color:white; font-family:sans-serif; }
.glass { background:rgba(30,41,59,.85); padding:30px; border-radius:20px; }
input, textarea { background:#1e293b; color:white; }
</style>
"""

LOGIN_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center">
<div class="glass w-full max-w-md">
<h2 class="text-3xl font-bold text-center mb-6">LOGIN</h2>
<form method="post" class="space-y-4">
<input name="tgid" placeholder="Telegram ID" required class="w-full p-3 rounded">
<input name="password" type="password" placeholder="Password" required class="w-full p-3 rounded">
<button class="w-full bg-cyan-500 text-black p-3 rounded font-bold">LOGIN</button>
</form>
</div>
</div>
"""

OTP_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center">
<div class="glass w-full max-w-sm text-center">
<h2 class="text-2xl font-bold mb-4">OTP VERIFY</h2>
<form method="post">
<input name="otp" placeholder="Enter OTP" required class="w-full p-3 rounded mb-4 text-center">
<button class="w-full bg-green-500 text-black p-3 rounded font-bold">VERIFY</button>
</form>
</div>
</div>
"""

DASH_HTML = BASE_HEAD + """
<div class="max-w-4xl mx-auto p-6">
<h2 class="text-3xl font-bold mb-6">Dashboard ({{uid}})</h2>

{% for bot, status in bots.items() %}
<div class="glass mb-4 flex justify-between items-center">
<span>{{bot}} - {{status}}</span>
{% if status == 'STOPPED' %}
<a href="/startbot/{{bot}}" class="bg-green-500 px-4 py-2 rounded text-black">START</a>
{% else %}
<a href="/stopbot/{{bot}}" class="bg-red-500 px-4 py-2 rounded">STOP</a>
{% endif %}
</div>
{% endfor %}

<form method="post" action="/upload" enctype="multipart/form-data" class="glass mt-6">
<input type="file" name="botfile" required>
<button class="bg-cyan-500 px-4 py-2 rounded text-black">UPLOAD</button>
</form>

<a href="/logout" class="block mt-6 text-red-400">Logout</a>
</div>
"""

# ================= ROUTES =================
@app.route("/", methods=["GET","POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
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
    cur.execute("SELECT 1 FROM approvals WHERE telegram_id=?", (uid,))
    if not cur.fetchone():
        return "Go to Telegram and send /approve"

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
        return "File too large (1MB)"

    files = [f for f in os.listdir(BOTS_DIR) if f.startswith(str(uid)+"_")]
    if not is_admin(uid) and len(files) >= 10:
        return "Slot full (Max 10 bots)"

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
        RUNNING_BOTS[bot] = subprocess.Popen([sys.executable, path])
    return redirect(url_for("dashboard"))

@app.route("/stopbot/<bot>")
def stopbot(bot):
    p = RUNNING_BOTS.get(bot)
    if p:
        p.terminate()
        RUNNING_BOTS.pop(bot, None)
    return redirect(url_for("dashboard"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=telegram_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
