import os, sys, ast, sqlite3, hashlib, subprocess, signal, time
from flask import Flask, request, redirect, session, render_template_string, url_for
from datetime import timedelta
import telebot

# ================= CONFIG =================
PORT = int(os.environ.get("PORT", 10000))
BOT_TOKEN = os.environ.get("PANEL_BOT_TOKEN")
OWNER_ID = int(os.environ.get("PANEL_ADMIN_ID"))
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")

DATA = "data"
BOTS = os.path.join(DATA, "bots")
LOGS = os.path.join(DATA, "logs")
os.makedirs(BOTS, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)

RUNNING = {}  # bot_name: Popen

# ================= DB =================
db = sqlite3.connect(os.path.join(DATA, "panel.db"), check_same_thread=False)
cur = db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
 telegram_id INTEGER PRIMARY KEY,
 password TEXT,
 approved INTEGER DEFAULT 0,
 banned INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS admins (
 telegram_id INTEGER PRIMARY KEY
)
""")

cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (OWNER_ID,))
db.commit()

def is_admin(uid):
    return cur.execute(
        "SELECT 1 FROM admins WHERE telegram_id=?", (uid,)
    ).fetchone() is not None

# ================= AUTO INSTALL =================
STD = {"os","sys","time","json","math","re","random","datetime","threading",
       "asyncio","subprocess","hashlib","sqlite3","signal","ast"}

def auto_install(py):
    try:
        tree = ast.parse(open(py, encoding="utf-8", errors="ignore").read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for m in n.names: mods.add(m.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        for p in mods:
            if p not in STD:
                subprocess.run(
                    [sys.executable,"-m","pip","install",p],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
    except Exception as e:
        print("install error:", e)

# ================= TELEGRAM BOT =================
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

@bot.message_handler(commands=["start"])
def tg_start(m):
    bot.send_message(m.chat.id, "Panel active.\nWebsite login karo.\n/approve bhejo.")

@bot.message_handler(commands=["approve"])
def tg_approve(m):
    cur.execute("UPDATE users SET approved=1 WHERE telegram_id=?", (m.from_user.id,))
    db.commit()
    bot.send_message(m.chat.id, "Approved! Website refresh karo.")

@bot.message_handler(commands=["users"])
def tg_users(m):
    if not is_admin(m.from_user.id): return
    rows = cur.execute("SELECT telegram_id,banned FROM users").fetchall()
    bot.send_message(m.chat.id, "\n".join([f"{u} | {b}" for u,b in rows]) or "No users")

@bot.message_handler(func=lambda m: True)
def tg_default(m):
    bot.send_message(m.chat.id, "Website use karo. /approve bhejo.")

# ================= WEB =================
app = Flask(__name__)
app.secret_key = "panel"
app.permanent_session_lifetime = timedelta(days=7)

BASE_HTML = """
<!doctype html>
<html>
<head>
<title>Python Hosting Panel</title>
<style>
body{margin:0;font-family:sans-serif;background:#0f172a;color:white}
.sidebar{width:220px;height:100vh;position:fixed;background:#020617;padding:20px}
.sidebar h2{color:#38bdf8}
.sidebar a{display:block;color:#cbd5f5;text-decoration:none;margin:10px 0}
.sidebar a:hover{color:#38bdf8}
.main{margin-left:240px;padding:30px}
.card{background:#020617;padding:20px;border-radius:12px;margin-bottom:20px;
transition:transform .3s}
.card:hover{transform:scale(1.02)}
button{background:#38bdf8;border:0;padding:8px 14px;border-radius:8px;cursor:pointer}
button:hover{background:#0ea5e9}
</style>
</head>
<body>
<div class="sidebar">
<h2>⚡ Panel</h2>
<a href="/dashboard">Dashboard</a>
<a href="/logout">Logout</a>
</div>
<div class="main">
{{content}}
</div>
</body>
</html>
"""

LOGIN = """
<div class="card">
<h2>Login</h2>
{% if session.get('need_approve') %}
<p style="color:#f87171">Telegram par /approve bhejo</p>
{% endif %}
<form method="post">
<input name="tgid" placeholder="Telegram ID"><br><br>
<input type="password" name="password" placeholder="Password"><br><br>
<button>Login</button>
</form>
</div>
"""

@app.route("/", methods=["GET","POST"])
def login():
    if session.get("user") and not session.get("need_approve"):
        return redirect("/dashboard")

    if request.method=="POST":
        uid=int(request.form["tgid"])
        pw=hashlib.sha256(request.form["password"].encode()).hexdigest()
        row=cur.execute("SELECT password,banned FROM users WHERE telegram_id=?", (uid,)).fetchone()
        if row and row[1]: return "Banned"
        if not row:
            cur.execute("INSERT INTO users VALUES (?,?,0,0)", (uid,pw))
            db.commit()
        if not row or row[0]==pw:
            session["user"]=uid
            if not is_admin(uid): session["need_approve"]=True
            return redirect("/dashboard")
    return render_template_string(BASE_HTML, content=LOGIN)

@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect("/")
    uid=session["user"]
    if not is_admin(uid):
        ok=cur.execute("SELECT approved FROM users WHERE telegram_id=?", (uid,)).fetchone()[0]
        if not ok:
            session["need_approve"]=True
            return redirect("/")
    session.pop("need_approve",None)

    files=[f for f in os.listdir(BOTS) if f.startswith(f"{uid}_")]
    content = "<div class='card'><h2>Upload Python</h2><form method='post' action='/upload' enctype='multipart/form-data'><input type='file' name='code'><br><br><button>Upload</button></form></div>"
    for f in files:
        content+=f"""
        <div class="card">
        <b>{f}</b><br><br>
        <a href="/start/{f}"><button>Start</button></a>
        <a href="/stop/{f}"><button>Stop</button></a>
        <a href="/restart/{f}"><button>Restart</button></a>
        <a href="/logs/{f}"><button>Logs</button></a>
        </div>
        """
    return render_template_string(BASE_HTML, content=content)

@app.route("/upload", methods=["POST"])
def upload():
    uid=session.get("user")
    if not uid: return redirect("/")
    f=request.files.get("code")
    if not f or not f.filename.endswith(".py"): return "Only .py"
    user_files=[x for x in os.listdir(BOTS) if x.startswith(f"{uid}_")]
    if not is_admin(uid) and len(user_files)>=3:
        return "Limit 3"
    path=os.path.join(BOTS, f"{uid}_{f.filename}")
    f.save(path)
    auto_install(path)
    return redirect("/dashboard")

def run_bot(name):
    path=os.path.join(BOTS,name)
    log=os.path.join(LOGS,name+".log")
    p=subprocess.Popen([sys.executable,path], stdout=open(log,"a"), stderr=subprocess.STDOUT)
    RUNNING[name]=p

@app.route("/start/<name>")
def start(name):
    if name not in RUNNING:
        run_bot(name)
    return redirect("/dashboard")

@app.route("/stop/<name>")
def stop(name):
    p=RUNNING.get(name)
    if p:
        p.terminate()
        RUNNING.pop(name)
    return redirect("/dashboard")

@app.route("/restart/<name>")
def restart(name):
    stop(name)
    time.sleep(1)
    run_bot(name)
    return redirect("/dashboard")

@app.route("/logs/<name>")
def logs(name):
    log=os.path.join(LOGS,name+".log")
    data=open(log).read() if os.path.exists(log) else "No logs"
    return f"<pre style='color:white'>{data}</pre><a href='/dashboard'>Back</a>"

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    update = telebot.types.Update.de_json(request.data.decode())
    bot.process_new_updates([update])
    return "OK"

if __name__=="__main__":
    if BASE_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{BASE_URL}/telegram")
    app.run("0.0.0.0", PORT)
