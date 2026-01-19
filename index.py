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
<div class="max-w-6xl mx-auto p-4 md:p-12 min-h-screen">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
        <div class="space-y-1">
            <h2 class="text-5xl font-black text-white tracking-tighter italic">
                KAALIX <span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">PRO</span>
            </h2>
            <div class="flex items-center gap-3">
                <div class="flex items-center gap-1.5 bg-slate-800/50 px-3 py-1 rounded-full border border-white/5">
                    <span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span>
                    <span class="text-slate-400 text-[10px] font-bold uppercase tracking-[0.2em]">{{uid}}</span>
                </div>
            </div>
        </div>
        <div class="flex gap-3 w-full md:w-auto">
            <a href="/logout" class="flex-1 md:flex-none text-center px-8 py-3 rounded-2xl bg-white/5 border border-white/10 text-white hover:bg-rose-500/20 hover:border-rose-500/50 transition-all duration-300 text-sm font-bold">
                Sign Out
            </a>
        </div>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-5 mb-10">
        <div class="relative group overflow-hidden bg-slate-900/40 backdrop-blur-xl p-8 rounded-[2.5rem] border border-white/5 hover:border-cyan-500/30 transition-all duration-500">
            <div class="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                <svg class="w-20 h-20 text-cyan-400" fill="currentColor" viewBox="0 0 24 24"><path d="M13 10V3L4 14h7v7l9-11h-7z"/></svg>
            </div>
            <p class="text-slate-500 text-xs font-black uppercase tracking-widest">Active Engines</p>
            <h4 class="text-5xl font-black text-white mt-3 flex items-baseline gap-2">
                {% set count = namespace(value=0) %}{% for b, s in bots.items() %}{% if s == 'RUNNING' %}{% set count.value = count.value + 1 %}{% endif %}{% endfor %}{{ count.value }}
                <span class="text-sm font-medium text-cyan-500/60 tracking-normal">Running Now</span>
            </h4>
        </div>

        <div class="bg-slate-900/40 backdrop-blur-xl p-8 rounded-[2.5rem] border border-white/5">
            <p class="text-slate-500 text-xs font-black uppercase tracking-widest">Resource Usage</p>
            <h4 class="text-5xl font-black text-white mt-3">{{ bots|length }}<span class="text-2xl text-slate-700">/3</span></h4>
            <div class="w-full bg-slate-800 h-1.5 mt-4 rounded-full overflow-hidden">
                <div class="bg-cyan-500 h-full transition-all duration-1000" style="width: {{ (bots|length / 3) * 100 }}%"></div>
            </div>
        </div>

        <div class="bg-gradient-to-br from-emerald-500/10 to-transparent backdrop-blur-xl p-8 rounded-[2.5rem] border border-emerald-500/20">
            <p class="text-emerald-500/70 text-xs font-black uppercase tracking-widest">Server Latency</p>
            <h4 class="text-5xl font-black text-emerald-400 mt-3">24<span class="text-xl">ms</span></h4>
            <p class="text-emerald-500/50 text-[10px] mt-2 font-bold uppercase">Optimal Performance</p>
        </div>
    </div>

    <div class="bg-slate-900/40 backdrop-blur-2xl rounded-[3rem] border border-white/5 shadow-3xl overflow-hidden mb-10">
        <div class="px-10 py-8 border-b border-white/5 flex justify-between items-center bg-white/[0.02]">
            <h3 class="font-black text-2xl tracking-tight">Active Projects</h3>
            <span class="bg-cyan-500/10 text-cyan-400 text-[10px] font-black px-4 py-1.5 rounded-full border border-cyan-500/20 uppercase tracking-widest">Live Updates</span>
        </div>
        
        <div class="p-6 md:p-10">
            {% if bots %}
                <div class="grid gap-4">
                {% for bot, status in bots.items() %}
                <div class="group flex flex-col md:flex-row items-center justify-between p-6 bg-slate-800/30 rounded-[2rem] border border-white/5 hover:bg-slate-800/60 hover:scale-[1.01] transition-all duration-300">
                    <div class="flex items-center gap-6 mb-6 md:mb-0 w-full md:w-auto">
                        <div class="relative">
                            <div class="w-14 h-14 rounded-2xl bg-slate-900 flex items-center justify-center border border-white/10 group-hover:border-cyan-500/50 transition-colors">
                                <svg class="w-6 h-6 {% if status=='RUNNING' %}text-cyan-400{% else %}text-slate-600{% endif %}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4"></path></svg>
                            </div>
                            {% if status=='RUNNING' %}
                                <span class="absolute -top-1 -right-1 w-4 h-4 bg-green-500 border-4 border-slate-900 rounded-full"></span>
                            {% endif %}
                        </div>
                        <div class="overflow-hidden">
                            <span class="font-bold text-lg text-slate-100 block truncate">{{bot}}</span>
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] uppercase font-black tracking-tighter {% if status=='RUNNING' %}text-emerald-400{% else %}text-slate-500{% endif %}">{{status}}</span>
                                <span class="text-slate-600 text-[10px]">•</span>
                                <span class="text-slate-600 text-[10px] uppercase font-bold">Instance #{{ loop.index }}</span>
                            </div>
                        </div>
                    </div>
                    
                    <div class="flex gap-3 w-full md:w-auto">
                        {% if status=='STOPPED' %}
                            <a href='/startbot/{{bot}}' class="flex-1 text-center bg-cyan-500 hover:bg-cyan-400 text-slate-950 px-8 py-3 rounded-xl text-xs font-black transition-all transform active:scale-95 shadow-lg shadow-cyan-500/20">RESUME</a>
                        {% else %}
                            <a href='/stopbot/{{bot}}' class="flex-1 text-center bg-white/5 hover:bg-rose-500 text-white px-8 py-3 rounded-xl text-xs font-black transition-all transform active:scale-95">TERMINATE</a>
                        {% endif %}
                        <a href='/editbot/{{bot}}' class="flex-1 text-center bg-slate-700/50 hover:bg-slate-600 text-white px-8 py-3 rounded-xl text-xs font-black transition-all">CONFIG</a>
                    </div>
                </div>
                {% endfor %}
                </div>
            {% else %}
                <div class="text-center py-20 bg-slate-800/20 rounded-[2rem] border-2 border-dashed border-white/5">
                    <div class="w-20 h-20 bg-slate-800 rounded-full flex items-center justify-center mx-auto mb-6">
                        <svg class="w-10 h-10 text-slate-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M12 6v6m0 0v6m0-6h6m-6 0H6"></path></svg>
                    </div>
                    <p class="text-slate-400 font-bold uppercase tracking-widest text-sm">No Active Deployments</p>
                    <p class="text-slate-600 text-xs mt-1">Upload your script below to get started.</p>
                </div>
            {% endif %}
        </div>
    </div>

    <div class="bg-gradient-to-r from-cyan-600/20 to-blue-600/20 p-1 md:p-1 rounded-[3.5rem]">
        <div class="bg-slate-950 p-8 md:p-12 rounded-[3.2rem]">
            <div class="flex flex-col lg:flex-row items-center gap-10">
                <div class="flex-1 text-center lg:text-left">
                    <h3 class="text-3xl font-black mb-3">Deploy New Core</h3>
                    <p class="text-slate-400 font-medium max-w-sm">Drag and drop your <span class="text-cyan-400">.py</span> or <span class="text-cyan-400">.zip</span> package here for instant deployment.</p>
                </div>
                <form method='post' action='/upload' enctype='multipart/form-data' class="w-full lg:w-auto flex flex-col md:flex-row gap-4">
                    <div class="relative group">
                        <input type='file' name='botfile' required class="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10">
                        <div class="bg-slate-900 border-2 border-dashed border-slate-700 group-hover:border-cyan-500/50 px-8 py-4 rounded-2xl transition-all flex items-center gap-4">
                            <svg class="w-5 h-5 text-slate-500 group-hover:text-cyan-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"></path></svg>
                            <span class="text-slate-400 group-hover:text-white text-sm font-bold">Choose System File</span>
                        </div>
                    </div>
                    <button class='bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-black px-12 py-5 rounded-2xl transition-all shadow-2xl shadow-cyan-500/20 transform active:scale-95 uppercase tracking-widest text-sm'>
                        Initialize
                    </button>
                </form>
            </div>
        </div>
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
