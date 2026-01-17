import os, sys, threading, subprocess, zipfile, random, hashlib, sqlite3
from datetime import datetime, timedelta
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
OWNER_ID = int(os.environ.get("PANEL_ADMIN_ID"))

if not BOT_TOKEN or not OWNER_ID:
    raise RuntimeError("Missing ENV variables")

# ================= DATABASE =================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
 telegram_id INTEGER PRIMARY KEY,
 password TEXT,
 verified INTEGER DEFAULT 0,
 banned INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS approvals (
 telegram_id INTEGER PRIMARY KEY
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS admins (
 telegram_id INTEGER PRIMARY KEY
)
""")

conn.commit()

# owner always admin
cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (OWNER_ID,))
conn.commit()

def is_admin(uid):
    return cur.execute(
        "SELECT 1 FROM admins WHERE telegram_id=?", (uid,)
    ).fetchone() is not None

# ================= TELEGRAM BOT =================
tg = telebot.TeleBot(BOT_TOKEN)
OTP_CACHE = {}
RUNNING_BOTS = {}

def send_otp(uid):
    otp = str(random.randint(100000, 999999))
    OTP_CACHE[uid] = otp
    tg.send_message(uid, f"OTP CODE: {otp}\nDo not share.")

@tg.message_handler(commands=["start"])
def start_cmd(m):
    tg.reply_to(m, "KAALIX Panel Bot Online")

@tg.message_handler(commands=["approve"])
def approve_cmd(m):
    cur.execute("INSERT OR IGNORE INTO approvals VALUES (?)", (m.from_user.id,))
    conn.commit()
    tg.reply_to(m, "Approved. Refresh website.")

# -------- ADMIN COMMANDS --------

@tg.message_handler(commands=["users"])
def users_cmd(m):
    if not is_admin(m.from_user.id): return
    rows = cur.execute("SELECT telegram_id,banned FROM users").fetchall()
    msg = "USERS:\n"
    for u,b in rows:
        msg += f"{u} | {'BANNED' if b else 'ACTIVE'}\n"
    tg.send_message(m.chat.id, msg or "No users")

@tg.message_handler(commands=["ban"])
def ban_cmd(m):
    if not is_admin(m.from_user.id): return
    try:
        uid = int(m.text.split()[1])
        cur.execute("UPDATE users SET banned=1 WHERE telegram_id=?", (uid,))
        conn.commit()
        tg.send_message(m.chat.id, f"Banned {uid}")
    except:
        tg.send_message(m.chat.id, "Usage: /ban <chat_id>")

@tg.message_handler(commands=["unban"])
def unban_cmd(m):
    if not is_admin(m.from_user.id): return
    try:
        uid = int(m.text.split()[1])
        cur.execute("UPDATE users SET banned=0 WHERE telegram_id=?", (uid,))
        conn.commit()
        tg.send_message(m.chat.id, f"Unbanned {uid}")
    except:
        tg.send_message(m.chat.id, "Usage: /unban <chat_id>")

@tg.message_handler(commands=["addadmin"])
def addadmin_cmd(m):
    if m.from_user.id != OWNER_ID: return
    try:
        uid = int(m.text.split()[1])
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
        conn.commit()
        tg.send_message(m.chat.id, f"Admin added: {uid}")
    except:
        tg.send_message(m.chat.id, "Usage: /addadmin <chat_id>")

@tg.message_handler(commands=["deladmin"])
def deladmin_cmd(m):
    if m.from_user.id != OWNER_ID: return
    try:
        uid = int(m.text.split()[1])
        if uid == OWNER_ID:
            tg.send_message(m.chat.id, "Owner cannot be removed")
            return
        cur.execute("DELETE FROM admins WHERE telegram_id=?", (uid,))
        conn.commit()
        tg.send_message(m.chat.id, f"Admin removed: {uid}")
    except:
        tg.send_message(m.chat.id, "Usage: /deladmin <chat_id>")

def telegram_polling():
    tg.infinity_polling(skip_pending=True)

# ================= FLASK APP =================
app = Flask(__name__)
app.secret_key = "kaalix_secret"
app.permanent_session_lifetime = timedelta(days=7)

BASE = "<script src='https://cdn.tailwindcss.com'></script>"

LOGIN_HTML = BASE + """
<div class="h-screen flex items-center justify-center bg-slate-900 text-white">
<form method="post" class="bg-slate-800 p-6 rounded w-80 space-y-3">
<h2 class="text-xl font-bold">Login</h2>
{% if session.get('need_approve') %}
<p class="text-red-400">Send /approve on Telegram</p>
{% endif %}
<input name="tgid" placeholder="Telegram ID" class="w-full p-2 bg-slate-700">
<input type="password" name="password" placeholder="Password" class="w-full p-2 bg-slate-700">
<button class="bg-cyan-500 w-full p-2 text-black">LOGIN</button>
</form></div>
"""

OTP_HTML = BASE + """
<div class="h-screen flex items-center justify-center bg-slate-900 text-white">
<form method="post" class="bg-slate-800 p-6 rounded w-80 space-y-3">
<h2 class="text-xl font-bold">OTP</h2>
<input name="otp" placeholder="Enter OTP" class="w-full p-2 bg-slate-700">
<button class="bg-green-500 w-full p-2 text-black">VERIFY</button>
</form></div>
"""

DASH_HTML = BASE + """
<div class="p-6 text-white bg-slate-900 min-h-screen">
<h2 class="text-2xl mb-4">Dashboard {{uid}}</h2>
{% for b,s in bots.items() %}
<div class="bg-slate-800 p-3 mb-2 flex justify-between">
<span>{{b}} ({{s}})</span>
{% if s=='STOPPED' %}
<a href="/startbot/{{b}}" class="text-green-400">START</a>
{% else %}
<a href="/stopbot/{{b}}" class="text-red-400">STOP</a>
{% endif %}
</div>
{% endfor %}
<form method="post" action="/upload" enctype="multipart/form-data">
<input type="file" name="botfile">
<button class="bg-cyan-500 p-2 text-black">UPLOAD</button>
</form>
<a href="/logout" class="block mt-4 text-red-400">Logout</a>
</div>
"""

@app.route("/", methods=["GET","POST"])
def login():
    if session.get("user"): return redirect("/dashboard")
    if request.method=="POST":
        uid = int(request.form["tgid"])
        pw = hashlib.sha256(request.form["password"].encode()).hexdigest()
        row = cur.execute("SELECT password,banned FROM users WHERE telegram_id=?", (uid,)).fetchone()
        if row and row[1]: return "You are banned"
        if not row:
            send_otp(uid)
            cur.execute("INSERT INTO users VALUES (?,?,0,0)", (uid,pw))
            conn.commit()
            session["pending"]=uid
            return redirect("/otp")
        if row[0]==pw:
            session["user"]=uid
            return redirect("/dashboard")
    return render_template_string(LOGIN_HTML)

@app.route("/otp", methods=["GET","POST"])
def otp():
    if "pending" not in session: return redirect("/")
    if request.method=="POST":
        uid=session["pending"]
        if OTP_CACHE.get(uid)==request.form["otp"]:
            cur.execute("UPDATE users SET verified=1 WHERE telegram_id=?", (uid,))
            conn.commit()
            session.pop("pending")
            session["user"]=uid
            return redirect("/dashboard")
    return render_template_string(OTP_HTML)

@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect("/")
    uid=session["user"]
    if not cur.execute("SELECT 1 FROM approvals WHERE telegram_id=?", (uid,)).fetchone():
        session["need_approve"]=True
        return redirect("/")
    session.pop("need_approve",None)
    bots={}
    for f in os.listdir(BOTS_DIR):
        if f.startswith(str(uid)+"_"):
            bots[f]="RUNNING" if f in RUNNING_BOTS else "STOPPED"
    return render_template_string(DASH_HTML,bots=bots,uid=uid)

@app.route("/upload", methods=["POST"])
def upload():
    uid=session.get("user")
    if not uid: return redirect("/")
    file=request.files.get("botfile")
    if not file: return "No file"
    files=[f for f in os.listdir(BOTS_DIR) if f.startswith(str(uid)+"_")]
    if not is_admin(uid) and len(files)>=10:
        return "Limit reached (10)"
    name=f"{uid}_{file.filename}"
    path=os.path.join(BOTS_DIR,name)
    file.save(path)
    return redirect("/dashboard")

@app.route("/startbot/<bot>")
def startbot(bot):
    RUNNING_BOTS[bot]=subprocess.Popen([sys.executable,os.path.join(BOTS_DIR,bot)])
    return redirect("/dashboard")

@app.route("/stopbot/<bot>")
def stopbot(bot):
    p=RUNNING_BOTS.pop(bot,None)
    if p: p.terminate()
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

if __name__ == "__main__":
    threading.Thread(target=telegram_polling, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)
