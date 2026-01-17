import os, sys, ast, sqlite3, hashlib, subprocess, time
from flask import Flask, request, redirect, session, render_template_string
from datetime import timedelta
import telebot

# ================= CONFIG =================
PORT = int(os.environ.get("PORT", 10000))
BOT_TOKEN = os.environ.get("PANEL_BOT_TOKEN")
OWNER_ID = int(os.environ.get("PANEL_ADMIN_ID"))
BASE_URL = os.environ.get("RENDER_EXTERNAL_URL")

APP_NAME = "PYTHON BOT HOSTING"

BOT_APPROVE_URL = "https://t.me/Mr_rocky_99_bot"
DEV_LINK = "https://t.me/DM_CRAKA_OWNER_BOT"
DEV_NAME = "C̶R̶A̶K̶A̶"

DATA="data"
BOTS=f"{DATA}/bots"
LOGS=f"{DATA}/logs"
os.makedirs(BOTS,exist_ok=True)
os.makedirs(LOGS,exist_ok=True)

RUNNING={}

# ================= DATABASE =================
db=sqlite3.connect(f"{DATA}/panel.db",check_same_thread=False)
cur=db.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users(
 telegram_id INTEGER PRIMARY KEY,
 password TEXT,
 approved INTEGER DEFAULT 0,
 banned INTEGER DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS admins(
 telegram_id INTEGER PRIMARY KEY
)
""")
cur.execute("INSERT OR IGNORE INTO admins VALUES (?)",(OWNER_ID,))
db.commit()

def is_admin(uid):
    return cur.execute(
        "SELECT 1 FROM admins WHERE telegram_id=?",(uid,)
    ).fetchone() is not None

# ================= AUTO INSTALL =================
SAFE={"os","sys","time","json","math","re","random","datetime",
      "threading","asyncio","subprocess","hashlib","sqlite3","signal","ast"}

def auto_install(path):
    try:
        tree=ast.parse(open(path,errors="ignore").read())
        mods=set()
        for n in ast.walk(tree):
            if isinstance(n,ast.Import):
                for m in n.names: mods.add(m.name.split(".")[0])
            elif isinstance(n,ast.ImportFrom) and n.module:
                mods.add(n.module.split(".")[0])
        for p in mods:
            if p not in SAFE:
                subprocess.run(
                    [sys.executable,"-m","pip","install",p],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
    except: pass

# ================= TELEGRAM BOT =================
bot=telebot.TeleBot(BOT_TOKEN,threaded=False)

@bot.message_handler(commands=["start"])
def tg_start(m):
    bot.send_message(
        m.chat.id,
        f"✅ {APP_NAME}\nApprove ke liye /approve bhejo."
    )

@bot.message_handler(commands=["approve"])
def tg_approve(m):
    cur.execute(
        "UPDATE users SET approved=1 WHERE telegram_id=?",
        (m.from_user.id,)
    )
    db.commit()
    bot.send_message(m.chat.id,"✅ Approved! Website refresh karo.")

# ================= FLASK =================
app=Flask(__name__)
app.secret_key="craka_panel"
app.permanent_session_lifetime=timedelta(days=7)

# ================= UI =================
BASE_HTML="""
<!doctype html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{{title}}</title>
<style>
body{margin:0;background:#020617;color:#e5e7eb;font-family:system-ui}
.snow{
position:fixed;inset:0;pointer-events:none;
background:url('https://i.imgur.com/NM8ZC2B.png');
animation:snow 20s linear infinite;opacity:.35
}
@keyframes snow{from{background-position:0 0}to{background-position:0 1000px}}
.card{
background:rgba(15,23,42,.8);
border-radius:18px;padding:20px;margin:15px
}
input{
width:100%;padding:10px;border-radius:12px;
border:0;margin-bottom:10px
}
button{
padding:10px 14px;border-radius:12px;
border:0;cursor:pointer;
background:linear-gradient(135deg,#a855f7,#38bdf8);
font-weight:700
}
.btn-red{background:#ef4444;color:#fff}
.footer{text-align:center;font-size:13px;opacity:.85}
.link-btn{
background:none;border:none;color:#a5b4fc;
font-weight:700;cursor:pointer
}
</style>
</head>
<body>
<div class="snow"></div>
<div style="max-width:520px;margin:auto">
{{body|safe}}
<div class="footer">
Developed by 
<a href="{{dev_link}}" target="_blank" style="color:#a855f7;font-weight:700">
{{dev}}
</a>
</div>
</div>
</body>
</html>
"""

def render_page(title,body):
    return render_template_string(
        BASE_HTML,
        title=title,
        body=body,
        dev=DEV_NAME,
        dev_link=DEV_LINK
    )

# ================= LOGIN =================
@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        uid=int(request.form["tgid"])
        pw=hashlib.sha256(request.form["password"].encode()).hexdigest()
        row=cur.execute(
            "SELECT password FROM users WHERE telegram_id=?",(uid,)
        ).fetchone()
        if not row:
            cur.execute("INSERT INTO users VALUES (?,?,0,0)",(uid,pw))
            db.commit()
        session["user"]=uid
        if not is_admin(uid):
            session["need_approve"]=True
        return redirect("/dashboard")

    return render_page("Login",f"""
    <div class='card'>
    <h2>{APP_NAME}</h2>
    <form method='post'>
      <input name='tgid' placeholder='Telegram ID'>
      <input type='password' name='password' placeholder='Password'>
      <button>Sign In</button>
    </form>
    </div>
    """)

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    uid=session.get("user")
    if not uid:
        return redirect("/")

    if session.get("need_approve"):
        return render_page("Approve",f"""
        <div class='card'>
        <h3>Approval Required</h3>
        <p>Telegram se approve karo</p>
        <a href="{BOT_APPROVE_URL}" target="_blank">
          <button>Approve Now</button>
        </a>
        </div>
        """)

    files=sorted([f for f in os.listdir(BOTS) if f.startswith(f"{uid}_")])

    popup=""
    if session.pop("uploaded",None):
        popup+="<script>alert('✅ Code uploaded successfully');</script>"
    if session.pop("deleted",None):
        popup+="<script>alert('🗑️ Code deleted successfully');</script>"

    body=popup+"""
    <div class='card'>
    <h3>Upload Python Bot</h3>
    <form method='post' action='/upload' enctype='multipart/form-data'>
      <input type='file' name='code' required>
      <button>Upload</button>
    </form>
    </div>

    <div class='card'>
    <h3>Delete Code</h3>
    <form method='post' action='/delete'>
      <input name='code_index' placeholder='Enter code number'>
      <button class='btn-red'>Delete</button>
    </form>
    </div>
    """

    for i,f in enumerate(files,1):
        running=f in RUNNING
        body+=f"""
        <div class='card'>
        <b>{i}. {f}</b><br><br>
        {"" if running else f"<a href='/start/{f}'><button>Start</button></a>"}
        {f"<a href='/stop/{f}'><button class='btn-red'>Stop</button></a>" if running else ""}
        {f"<a href='/restart/{f}'><button>Restart</button></a>" if running else ""}
        {f"<a href='/logs/{f}'><button>Logs</button></a>" if running else ""}
        </div>
        """

    return render_page("Dashboard",body)

# ================= UPLOAD =================
@app.route("/upload",methods=["POST"])
def upload():
    uid=session.get("user")
    if not uid: return redirect("/")
    files=[f for f in os.listdir(BOTS) if f.startswith(f"{uid}_")]
    if not is_admin(uid) and len(files)>=3:
        return "Limit reached"
    f=request.files.get("code")
    if not f or not f.filename.endswith(".py"):
        return "Only .py allowed"
    path=f"{BOTS}/{uid}_{f.filename}"
    f.save(path)
    auto_install(path)
    session["uploaded"]=True
    return redirect("/dashboard")

# ================= DELETE =================
@app.route("/delete",methods=["POST"])
def delete():
    uid=session.get("user")
    idx=request.form.get("code_index","")
    if not idx.isdigit(): return redirect("/dashboard")
    idx=int(idx)-1
    files=sorted([f for f in os.listdir(BOTS) if f.startswith(f"{uid}_")])
    if idx<0 or idx>=len(files): return redirect("/dashboard")
    name=files[idx]
    if name in RUNNING:
        RUNNING[name].terminate()
        RUNNING.pop(name)
    try: os.remove(f"{BOTS}/{name}")
    except: pass
    log=f"{LOGS}/{name}.log"
    if os.path.exists(log): os.remove(log)
    session["deleted"]=True
    return redirect("/dashboard")

# ================= PROCESS =================
def run_bot(name):
    RUNNING[name]=subprocess.Popen(
        [sys.executable,f"{BOTS}/{name}"],
        stdout=open(f"{LOGS}/{name}.log","a"),
        stderr=subprocess.STDOUT
    )

@app.route("/start/<n>")
def start(n):
    if n not in RUNNING: run_bot(n)
    return redirect("/dashboard")

@app.route("/stop/<n>")
def stop(n):
    if n in RUNNING:
        RUNNING[n].terminate()
        RUNNING.pop(n)
    return redirect("/dashboard")

@app.route("/restart/<n>")
def restart(n):
    if n in RUNNING:
        RUNNING[n].terminate()
        RUNNING.pop(n)
    time.sleep(1); run_bot(n)
    return redirect("/dashboard")

@app.route("/logs/<n>")
def logs(n):
    log=f"{LOGS}/{n}.log"
    data=open(log).read() if os.path.exists(log) else ""
    return render_page("Logs",f"<pre>{data}</pre>")

# ================= TELEGRAM WEBHOOK =================
@app.route("/telegram",methods=["POST"])
def telegram():
    bot.process_new_updates([
        telebot.types.Update.de_json(request.data.decode())
    ])
    return "OK"

# ================= START =================
if __name__=="__main__":
    if BASE_URL:
        bot.remove_webhook()
        bot.set_webhook(url=f"{BASE_URL}/telegram")
    app.run("0.0.0.0",PORT)
