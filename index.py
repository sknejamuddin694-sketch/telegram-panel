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
import re
import time

PORT = 8080
DATA_DIR = "data"
BOTS_DIR = os.path.join(DATA_DIR, "bots")
DB_FILE = os.path.join(DATA_DIR, "panel.db")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(BOTS_DIR, exist_ok=True)

BOT_TOKEN = "8440660703:AAHppsz0_NZzbyxU91vHM5W54CD_Xy_G5WA"
ADMIN_ID = 8465446299

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
PUBLIC_URL = None


def send_otp(tg_id):
    otp = str(random.randint(100000, 999999))
    OTP_CACHE[tg_id] = otp
    try:
        tg.send_message(
            tg_id,
            f"🛡️ *KAALIX SECURITY*\n\nYour Login OTP: `{otp}`\n\nDon't share this code.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("OTP send error:", e)


@tg.message_handler(commands=["start"])
def tg_start(msg):
    if PUBLIC_URL:
        tg.reply_to(
            msg,
            f"🚀 KAALIX Premium Panel Bot is Online\n\n🌐 Panel Link:\n{PUBLIC_URL}"
        )
    else:
        tg.reply_to(
            msg,
            "🚀 KAALIX Premium Panel Bot is Online\n\n⏳ Panel starting, link coming soon..."
        )


@tg.message_handler(commands=["approve"])
def tg_approve(msg):
    APPROVE_CACHE[msg.from_user.id] = True
    tg.reply_to(msg, "✅ Access Approved! You can now use the dashboard.")


@tg.message_handler(commands=["panel"])
def tg_panel(msg):
    if PUBLIC_URL:
        tg.reply_to(msg, f"🌐 Panel URL:\n{PUBLIC_URL}")
    else:
        tg.reply_to(msg, "⏳ Panel is starting, please wait...")


def telegram_polling():
    tg.infinity_polling()

# ---------------- FLASK APP & UI ----------------
app = Flask(__name__)
app.secret_key = "kaalix_secret_key_123"
app.permanent_session_lifetime = timedelta(days=7)

# ------------------- HTML & CSS -------------------
BASE_HEAD = """
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap" rel="stylesheet">
<style>
    body { font-family: 'Inter', sans-serif; background: #0f172a; color: #f8fafc; }
    .glass { background: rgba(30, 41, 59, 0.7); backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.1); }
    .btn-glow:hover { box-shadow: 0 0 20px rgba(34, 211, 238, 0.4); transform: translateY(-1px); }
    input { background: #1e293b !important; border: 1px solid #334155 !important; color: white !important; }
    .animate-pulse-fast { animation: pulse 1.5s cubic-bezier(0.4, 0, 0.6, 1) infinite; }
</style>
"""

# ---------------- HTML TEMPLATES -------------------
LOGIN_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center p-4">
    <div class="glass w-full max-w-md p-10 rounded-3xl shadow-2xl">
        <div class="text-center mb-8">
            <h2 class="text-4xl font-black text-cyan-400 tracking-tighter">KAALIX</h2>
            <p class="text-slate-400 text-sm mt-1">Authorized Access Only</p>
        </div>
        <form method="post" class="space-y-6">
            <div>
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Telegram ID</label>
                <input name="tgid" required class="w-full px-4 py-3 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500 transition-all">
            </div>
            <div>
                <label class="block text-xs font-semibold uppercase tracking-wider text-slate-500 mb-2">Password</label>
                <input name="password" type="password" required class="w-full px-4 py-3 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500 transition-all">
            </div>
            <div class="flex items-center">
                <input type="checkbox" name="remember" id="rem" class="w-4 h-4 rounded border-gray-300">
                <label for="rem" class="ml-2 text-sm text-slate-400">Keep me logged in</label>
            </div>
            <button class="w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold py-4 rounded-xl transition-all btn-glow shadow-lg shadow-cyan-500/20">
                ENTER PANEL
            </button>
        </form>
    </div>
</div>
"""

OTP_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center p-4">
    <div class="glass w-full max-w-sm p-10 rounded-3xl text-center shadow-2xl">
        <div class="inline-flex items-center justify-center w-16 h-16 rounded-full bg-cyan-500/10 mb-6">
            <span class="text-3xl">🔑</span>
        </div>
        <h3 class="text-2xl font-bold text-white mb-2">Security Verification</h3>
        <p class="text-slate-400 mb-8 text-sm">We've sent a 6-digit code to your Telegram.</p>
        <form method="post" class="space-y-4">
            <input name="otp" placeholder="000000" maxlength="6" class="w-full text-center text-3xl font-mono tracking-[0.5em] px-4 py-4 rounded-xl outline-none focus:ring-2 focus:ring-cyan-500">
            <button class="w-full bg-cyan-500 text-slate-950 font-bold py-4 rounded-xl hover:bg-cyan-400 transition-all shadow-lg">VERIFY CODE</button>
        </form>
    </div>
</div>
"""

DASH_HTML = BASE_HEAD + """
<div class="max-w-5xl mx-auto p-4 md:p-10">
    <div class="flex flex-col md:flex-row justify-between items-center mb-12 gap-6">
        <div>
            <h2 class="text-4xl font-black text-white tracking-tighter">KAALIX <span class="text-cyan-400">PANEL</span></h2>
            <div class="flex items-center gap-2 mt-1">
                <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                <p class="text-slate-400 text-sm font-medium uppercase tracking-widest">Active Session: {{uid}}</p>
            </div>
        </div>
        <a href="/logout" class="px-6 py-2.5 rounded-xl border border-rose-500/30 text-rose-400 hover:bg-rose-500 hover:text-white transition-all text-sm font-bold">Logout</a>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-12">
        <div class="glass p-8 rounded-3xl relative overflow-hidden">
            <p class="text-slate-400 text-xs font-bold uppercase tracking-widest">Active Bots</p>
            <p class="text-4xl font-black text-cyan-400 mt-2">
                {% set count = namespace(value=0) %}{% for b, s in bots.items() %}{% if s == 'RUNNING' %}{% set count.value = count.value + 1 %}{% endif %}{% endfor %}{{ count.value }}
            </p>
        </div>
        <div class="glass p-8 rounded-3xl">
            <p class="text-slate-400 text-xs font-bold uppercase tracking-widest">Used Slots</p>
            <p class="text-4xl font-black text-white mt-2">{{ bots|length }} <span class="text-lg text-slate-500">/ 3</span></p>
        </div>
        <div class="glass p-8 rounded-3xl bg-gradient-to-br from-cyan-500/5 to-transparent">
            <p class="text-slate-400 text-xs font-bold uppercase tracking-widest">System Status</p>
            <p class="text-4xl font-black text-emerald-400 mt-2">ONLINE</p>
        </div>
    </div>

    <div class="glass rounded-[2rem] overflow-hidden mb-12 shadow-2xl">
        <div class="px-8 py-6 border-b border-white/5 bg-white/5">
            <h3 class="font-bold text-xl">My Projects</h3>
        </div>
        <div class="p-8">
            {% if bots %}
                <div class="grid gap-4">
                {% for bot, status in bots.items() %}
                <div class="flex flex-col md:flex-row items-center justify-between p-5 bg-slate-800/40 rounded-2xl border border-white/5 hover:border-cyan-500/30 transition-all">
                    <div class="flex items-center gap-4 mb-4 md:mb-0">
                        <div class="w-3 h-3 rounded-full {% if status=='RUNNING' %}bg-green-500 animate-pulse-fast shadow-[0_0_10px_rgba(34,197,94,0.5)]{% else %}bg-slate-600{% endif %}"></div>
                        <div>
                            <span class="font-mono text-sm font-semibold text-slate-200 block truncate max-w-[200px]">{{bot}}</span>
                            <span class="text-[10px] uppercase font-bold text-slate-500">{{status}}</span>
                        </div>
                    </div>
                    <div class="flex gap-3 w-full md:w-auto">
                        {% if status=='STOPPED' %}
                            <a href='/startbot/{{bot}}' class="flex-1 text-center bg-emerald-500 hover:bg-emerald-400 text-slate-950 px-5 py-2.5 rounded-xl text-xs font-black transition-all">START</a>
                        {% else %}
                            <a href='/stopbot/{{bot}}' class="flex-1 text-center bg-rose-500 hover:bg-rose-400 text-white px-5 py-2.5 rounded-xl text-xs font-black transition-all">STOP</a>
                        {% endif %}
                        <a href='/editbot/{{bot}}' class="flex-1 text-center bg-slate-700 hover:bg-slate-600 text-white px-5 py-2.5 rounded-xl text-xs font-black transition-all">EDIT</a>
                    </div>
                </div>
                {% endfor %}
                </div>
            {% else %}
                <div class="text-center py-16">
                    <div class="text-5xl mb-4 opacity-20">📂</div>
                    <p class="text-slate-500 font-medium">No bots found in your directory.</p>
                </div>
            {% endif %}
        </div>
    </div>

    <div class="glass p-10 rounded-[2rem] border-2 border-dashed border-cyan-500/20 bg-cyan-500/[0.02]">
        <h3 class="text-xl font-bold mb-2">Deploy New Bot</h3>
        <p class="text-slate-400 text-sm mb-6">Upload .py or .zip file (Max 1MB)</p>
        <form method='post' action='/upload' enctype='multipart/form-data' class="flex flex-col md:flex-row gap-4">
            <input type='file' name='botfile' required class="flex-1 text-sm text-slate-400 file:mr-4 file:py-3 file:px-6 file:rounded-xl file:border-0 file:text-xs file:font-black file:bg-cyan-500 file:text-slate-950 hover:file:bg-cyan-400 cursor-pointer">
            <button class='bg-white hover:bg-slate-200 text-slate-950 font-black px-10 py-4 rounded-xl transition-all shadow-xl'>DEPLOY</button>
        </form>
    </div>
</div>
"""

EDIT_HTML = BASE_HEAD + """
<div class="max-w-6xl mx-auto p-4 md:p-10">
    <div class="flex items-center justify-between mb-8">
        <div class="flex items-center gap-4">
            <a href="/dashboard" class="w-10 h-10 flex items-center justify-center rounded-full bg-slate-800 text-white hover:bg-slate-700">←</a>
            <h2 class="text-2xl font-bold">Edit <span class="text-cyan-400">{{botname}}</span></h2>
        </div>
    </div>
    <form method='post' class="space-y-6">
        <div class="glass p-4 rounded-3xl">
            <textarea name='code' spellcheck="false" class='w-full h-[60vh] p-6 bg-[#0a0f1a] text-cyan-300 font-mono text-sm rounded-2xl border border-white/5 focus:ring-1 focus:ring-cyan-500 outline-none shadow-inner'>{{code}}</textarea>
        </div>
        <button class='w-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black py-5 rounded-2xl shadow-2xl shadow-cyan-500/20 transition-all text-lg'>SAVE & UPDATE BOT</button>
    </form>
</div>
"""
# ---------------- FLASK ROUTES -------------------

@app.route("/", methods=["GET", "POST"])
def login():
    if session.get("user"):
        return redirect(url_for("dashboard"))
    if request.method=="POST":
        try:
            tgid = int(request.form.get("tgid"))
            password = request.form.get("password")
            remember = request.form.get("remember")
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
                if remember: session.permanent = True
                return redirect(url_for("dashboard"))
        except: pass
    return render_template_string(LOGIN_HTML)

@app.route("/otp", methods=["GET","POST"])
def otp():
    if "pending" not in session: return redirect(url_for("login"))
    if request.method=="POST":
        code = request.form.get("otp")
        tgid = session["pending"]
        if OTP_CACHE.get(tgid) == code:
            cur.execute("UPDATE users SET verified=1 WHERE telegram_id=?", (tgid,))
            conn.commit()
            session.pop("pending")
            session["user"] = tgid
            return redirect(url_for("dashboard"))
    return render_template_string(OTP_HTML)

@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect(url_for("login"))
    uid = session["user"]
    if not APPROVE_CACHE.get(uid):
        return f"{BASE_HEAD}<div class='min-h-screen flex items-center justify-center p-6'><div class='glass p-10 rounded-3xl text-center'><h2 class='text-2xl font-bold mb-4 text-amber-400'>Approval Required</h2><p class='text-slate-400 mb-6'>Please go to your Telegram bot and type <b>/approve</b></p><a href='#' onclick='window.location.reload()' class='text-cyan-400 font-bold underline'>Already Approved? Refresh here</a></div></div>"
    
    user_bots = {}
    files = [f for f in os.listdir(BOTS_DIR) if f.startswith(str(uid)+"_")]
    for f in files:
        user_bots[f] = "RUNNING" if f in RUNNING_BOTS else "STOPPED"
    return render_template_string(DASH_HTML, bots=user_bots, uid=uid)

@app.route("/upload", methods=["POST"])
def upload():
    if "user" not in session: return redirect(url_for("login"))
    uid = session["user"]
    file = request.files["botfile"]
    if not file: return "No file"
    
    file.seek(0,2); size = file.tell(); file.seek(0)
    if size > 1024*1024: return "File too large"
    
    files = [f for f in os.listdir(BOTS_DIR) if f.startswith(str(uid)+"_")]
    if len(files) >= 3: return "Slot full (Max 3 bots)"
    
    filename = f"{uid}_{file.filename}"
    path = os.path.join(BOTS_DIR, filename)
    file.save(path)
    
    if filename.endswith(".zip"):
        with zipfile.ZipFile(path) as z: z.extractall(BOTS_DIR)
        os.remove(path)
        
    cur.execute("INSERT INTO uploads VALUES (?,?,?,?)", (uid, filename, size, datetime.now().isoformat()))
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
        try: p.terminate()
        except: pass
        RUNNING_BOTS.pop(bot, None)
    return redirect(url_for("dashboard"))

@app.route("/editbot/<bot>", methods=["GET","POST"])
def editbot(bot):
    if "user" not in session: return redirect(url_for("login"))
    path = os.path.join(BOTS_DIR, bot)
    if request.method == "POST":
        code = request.form.get("code")
        with open(path, "w", encoding="utf-8") as f: f.write(code)
        return redirect(url_for("dashboard"))
    
    with open(path, "r", encoding="utf-8") as f: code = f.read()
    return render_template_string(EDIT_HTML, botname=bot, code=code)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ---------------- MAIN -------------------
if __name__ == "__main__":
    print("🚀 Starting KAALIX Panel...")

    # Telegram bot polling
    threading.Thread(target=telegram_polling, daemon=True).start()

    # Cloudflare tunnel with auto-send link
    def start_cloudflare_blocking():
        global PUBLIC_URL
        print("🌐 Starting Cloudflare Tunnel...")

        process = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://127.0.0.1:{PORT}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        for line in process.stdout:
            line = line.strip()
            print(line)
            match = re.search(r"https://[a-zA-Z0-9\-]+\.trycloudflare\.com", line)
            if match:
                PUBLIC_URL = match.group(0)
                print(f"✅ Public URL Generated: {PUBLIC_URL}")

                # AUTO SEND LINK TO ADMIN
                try:
                    tg.send_message(
                        ADMIN_ID,
                        f"🚀 *KAALIX PANEL LIVE*\n\n🌐 Panel Link:\n{PUBLIC_URL}",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print("Telegram send error:", e)
                break

    threading.Thread(target=start_cloudflare_blocking, daemon=True).start()

    # Start Flask panel
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
