import os, sys, ast, sqlite3, hashlib, subprocess, time
from flask import Flask, request, redirect, session, render_template_string
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

RUNNING = {}

# ================= DATABASE =================
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
STD = {
    "os","sys","time","json","math","re","random","datetime",
    "threading","asyncio","subprocess","hashlib","sqlite3","signal","ast"
}

def auto_install(pyfile):
    try:
        tree = ast.parse(open(pyfile, encoding="utf-8", errors="ignore").read())
        modules = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                for m in n.names:
                    modules.add(m.name.split(".")[0])
            elif isinstance(n, ast.ImportFrom) and n.module:
                modules.add(n.module.split(".")[0])

        for pkg in modules:
            if pkg not in STD:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", pkg],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
    except:
        pass

# ================= TELEGRAM BOT =================
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

@bot.message_handler(commands=["start"])
def tg_start(m):
    bot.send_message(
        m.chat.id,
        "✅ Panel Bot Active\n\nWebsite login karo.\nApprove ke liye /approve bhejo."
    )

@bot.message_handler(commands=["approve"])
def tg_approve(m):
    cur.execute(
        "UPDATE users SET approved=1 WHERE telegram_id=?",
        (m.from_user.id,)
    )
    db.commit()
    bot.send_message(m.chat.id, "✅ Approved! Website refresh karo.")

@bot.message_handler(func=lambda m: True)
def tg_default(m):
    bot.send_message(m.chat.id, "ℹ️ Website use karo. /approve bhejo.")

# ================= FLASK APP =================
app = Flask(__name__)
app.secret_key = "panel_secret_key"
app.permanent_session_lifetime = timedelta(days=7)

# ================= UI =================
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<title>{{title}}</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
<style>
*{box-sizing:border-box}
body{
 margin:0;font-family:Inter;
 background:
 radial-gradient(circle at top,#7c3aed 0%,#020617 40%),
 linear-gradient(#020617,#020617);
 color:#e5e7eb;
}
.sidebar{
 position:fixed;left:0;top:0;height:100vh;width:240px;
 background:rgba(2,6,23,.9);
 border-right:1px solid rgba(255,255,255,.08);
 padding:22px;
}
.logo{
 font-size:22px;font-weight:700;color:#a855f7;margin-bottom:30px;
}
.sidebar a{
 display:block;padding:10px 14px;border-radius:12px;
 color:#c7d2fe;text-decoration:none;margin-bottom:8px;
 transition:.2s;
}
.sidebar a:hover{
 background:rgba(168,85,247,.15);
}
.main{
 margin-left:260px;padding:30px;
}
.card{
 background:rgba(15,23,42,.6);
 backdrop-filter:blur(14px);
 border:1px solid rgba(255,255,255,.08);
 border-radius:20px;
 padding:22px;margin-bottom:20px;
}
input{
 width:100%;padding:12px;border-radius:14px;
 background:#020617;border:1px solid #1e293b;
 color:#e5e7eb;margin-bottom:14px;
}
button{
 padding:10px 16px;border-radius:12px;
 background:linear-gradient(135deg,#a855f7,#38bdf8);
 border:0;color:#020617;font-weight:700;
 cursor:pointer;
}
.btn-red{background:#ef4444;color:#fff}
.btn-gray{background:#475569;color:#fff}
pre{
 background:#020617;padding:16px;border-radius:14px;
 border:1px solid #1e293b;overflow:auto;
}
.center{
 min-height:100vh;display:flex;align-items:center;justify-content:center;
}
</style>
</head>
<body>
{% if session.get("user") %}
<div class="sidebar">
 <div class="logo">⚡ Python Panel</div>
 <a href="/dashboard">Dashboard</a>
 <a href="/logout">Logout</a>
</div>
{% endif %}
<div class="{% if session.get('user') %}main{% else %}center{% endif %}">
{{body|safe}}
</div>
</body>
</html>
"""

def render_page(title, body):
    return render_template_string(BASE_HTML, title=title, body=body)

# ================= LOGIN =================
@app.route("/", methods=["GET","POST"])
def login():
    if session.get("user"):
        return redirect("/dashboard")

    if request.method=="POST":
        uid = int(request.form["tgid"])
        pw = hashlib.sha256(request.form["password"].encode()).hexdigest()

        row = cur.execute(
            "SELECT password,approved,banned FROM users WHERE telegram_id=?",
            (uid,)
        ).fetchone()

        if row and row[2]:
            return "❌ Banned"

        if not row:
            cur.execute(
                "INSERT INTO users VALUES (?,?,0,0)",
                (uid,pw)
            )
            db.commit()
            session["need_approve"] = True
        else:
            if row[0] != pw:
                return "❌ Wrong password"
            if not row[1] and not is_admin(uid):
                session["need_approve"] = True

        session["user"] = uid
        return redirect("/dashboard")

    body = """
    <div class="card" style="width:420px">
    <h2>Sign In</h2>
    {% if session.get('need_approve') %}
    <p style="color:#f87171">Telegram par <b>/approve</b> bhejo</p>
    {% endif %}
    <form method="post">
      <input name="tgid" placeholder="Telegram ID">
      <input type="password" name="password" placeholder="Password">
      <button>Sign In</button>
    </form>
    </div>
    """
    return render_page("Login", render_template_string(body))

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    uid = session.get("user")
    if not uid:
        return redirect("/")

    if not is_admin(uid):
        ok = cur.execute(
            "SELECT approved FROM users WHERE telegram_id=?",
            (uid,)
        ).fetchone()[0]
        if not ok:
            return redirect("/")

    files = [f for f in os.listdir(BOTS) if f.startswith(f"{uid}_")]

    body = """
    <div class="card">
    <h3>Upload Python Bot</h3>
    <form method="post" action="/upload" enctype="multipart/form-data">
      <input type="file" name="code" required>
      <button>Upload</button>
    </form>
    </div>
    """

    for f in files:
        body += f"""
        <div class="card">
        <b>{f}</b><br><br>
        <a href="/start/{f}"><button>Start</button></a>
        <a href="/stop/{f}"><button class="btn-red">Stop</button></a>
        <a href="/restart/{f}"><button class="btn-gray">Restart</button></a>
        <a href="/logs/{f}"><button class="btn-gray">Logs</button></a>
        </div>
        """

    return render_page("Dashboard", body)

# ================= UPLOAD =================
@app.route("/upload", methods=["POST"])
def upload():
    uid = session.get("user")
    if not uid:
        return redirect("/")

    files = [x for x in os.listdir(BOTS) if x.startswith(f"{uid}_")]
    if not is_admin(uid) and len(files) >= 3:
        return "❌ Limit reached"

    f = request.files.get("code")
    if not f or not f.filename.endswith(".py"):
        return "❌ Only .py allowed"

    path = os.path.join(BOTS, f"{uid}_{f.filename}")
    f.save(path)
    auto_install(path)
    return redirect("/dashboard")

# ================= PROCESS CONTROL =================
def run_bot(name):
    path = os.path.join(BOTS, name)
    log = os.path.join(LOGS, name+".log")
    p = subprocess.Popen(
        [sys.executable, path],
        stdout=open(log,"a"),
        stderr=subprocess.STDOUT
    )
    RUNNING[name] = p

@app.route("/start/<name>")
def start(name):
    if name not in RUNNING:
        run_bot(name)
    return redirect("/dashboard")

@app.route("/stop/<name>")
def stop(name):
    p = RUNNING.get(name)
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
    log = os.path.join(LOGS, name+".log")
    data = open(log).read() if os.path.exists(log) else "No logs"
    return render_page("Logs", f"<pre>{data}</pre><br><a href='/dashboard'><button>Back</button></a>")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= TELEGRAM WEBHOOK =================
@app.route("/telegram", methods=["POST"])
def telegram():
    update = telebot.types.Update.de_json(request.data.decode())
    bot.process_new_updates([update])
    return "OK"

# ================= START =================
if __name__ == "__main__":
    if BASE_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{BASE_URL}/telegram")
    app.run("0.0.0.0", PORT)
