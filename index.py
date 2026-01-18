import os, subprocess
from flask import Flask, request, session, redirect, render_template_string
import telebot
from telebot.types import Update

# ============ CONFIG ============
BOT_TOKEN = "8507388502:AAFN-A33sRl6uqfy--EShYHXtuhisY06Z9k"
OWNER_ID = "8465446299"   # owner chat id
APPROVE_BOT = "https://t.me/Mr_rocky_99_bot"

USER_LIMIT = 3
DATA = "data"
BOTS = f"{DATA}/bots"
LOGS = f"{DATA}/logs"

os.makedirs(BOTS, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)

RUNNING = {}        # filename -> Popen
APPROVED = set()    # approved chat ids (runtime memory)

app = Flask(__name__)
app.secret_key = "craka-secure-panel"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ============ TELEGRAM (NO POLLING, NO WEBHOOK SET HERE) ============
@bot.message_handler(commands=["start"])
def tg_start(m):
    bot.send_message(
        m.chat.id,
        "Panel connected ✅\nApprove ke liye /approve"
    )

@bot.message_handler(commands=["approve"])
def tg_approve(m):
    APPROVED.add(str(m.chat.id))
    bot.send_message(m.chat.id, "✅ Approved! Website refresh karo")

@app.route("/telegram", methods=["POST"])
def telegram():
    update = Update.de_json(request.data.decode("utf-8"), bot)
    bot.process_new_updates([update])
    return "OK"

# ============ UI BASE ============
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Python Bot Hosting</title>
<style>
*{font-weight:700}
body{
 margin:0;
 background:linear-gradient(135deg,#2b1055,#000);
 color:white;
 font-family:Arial;
 overflow:hidden;
}
.snow{
 position:fixed; inset:0;
 background:url('https://i.imgur.com/NM8ZC2B.png');
 opacity:.25;
 animation:snow 25s linear infinite;
}
@keyframes snow{
 from{background-position:0 0}
 to{background-position:0 1200px}
}
.card{
 background:rgba(255,255,255,.08);
 padding:20px;
 border-radius:14px;
 width:320px;
 margin:12vh auto;
 box-shadow:0 0 25px rgba(0,0,0,.5);
}
input,textarea,button{
 width:100%;
 padding:10px;
 margin:6px 0;
 border-radius:8px;
 border:none;
 font-family:monospace;
}
textarea{height:260px}
button{
 background:#8b5cf6;
 color:white;
 font-weight:800;
 cursor:pointer;
}
.btn-red{background:#ef4444}
.btn-gray{background:#6b7280}
a{text-decoration:none}
.footer{
 position:fixed;
 bottom:10px;
 width:100%;
 text-align:center;
 font-size:20px;
 font-weight:900;
}
</style>
</head>
<body>
<div class="snow"></div>
{{body|safe}}
<div class="footer">
Developed By
<span onclick="window.open('https://t.me/DM_CRAKA_OWNER_BOT','_blank')"
style="cursor:pointer;text-decoration:underline">
C̶R̶A̶K̶A̶
</span>
</div>
</body>
</html>
"""

def render(body):
    return render_template_string(BASE_HTML, body=body)

# ============ LOGIN ============
@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        uid = request.form.get("tgid", "").strip()
        if not uid:
            return redirect("/")
        if uid not in APPROVED:
            return render(f"""
            <div class="card">
              <h3>Approval Required</h3>
              <p>Telegram bot par /approve bhejo</p>
              <a href="{APPROVE_BOT}" target="_blank">
                <button>Open Bot</button>
              </a>
            </div>
            """)
        session["uid"] = uid
        return redirect("/dashboard")

    return render("""
    <div class="card">
      <h3>Sign In</h3>
      <form method="post">
        <input name="tgid" placeholder="Telegram ID" required>
        <input type="password" placeholder="Password">
        <button>Sign In</button>
      </form>
    </div>
    """)

# ============ DASHBOARD ============
@app.route("/dashboard")
def dashboard():
    uid = session.get("uid")
    if not uid:
        return redirect("/")

    files = [f for f in os.listdir(BOTS) if f.startswith(uid + "_")]
    limit = 999 if uid == OWNER_ID else USER_LIMIT

    body = f"""
    <div class="card">
      <h3>Your Bots ({len(files)}/{limit})</h3>
    """

    for i, f in enumerate(files, 1):
        running = f in RUNNING
        body += f"""
        <hr>
        <b>{i}. {f}</b><br>
        {'' if running else f'<a href="/start/{f}"><button>Start</button></a>'}
        {f'<a href="/stop/{f}"><button class="btn-red">Stop</button></a>' if running else ''}
        {f'<a href="/restart/{f}"><button>Restart</button></a>' if running else ''}
        <a href="/edit/{f}"><button>Edit</button></a>
        <a href="/logs/{f}"><button class="btn-gray">Logs</button></a>
        <a href="/delete/{f}"><button class="btn-red">Delete</button></a>
        """

    body += """
      <form method="post" action="/upload" enctype="multipart/form-data">
        <input type="file" name="code" required>
        <button>Upload</button>
      </form>
      <a href="/logout"><button class="btn-gray">Logout</button></a>
    </div>
    """
    return render(body)

# ============ UPLOAD ============
@app.route("/upload", methods=["POST"])
def upload():
    uid = session.get("uid")
    if not uid:
        return redirect("/")

    files = [f for f in os.listdir(BOTS) if f.startswith(uid + "_")]
    if uid != OWNER_ID and len(files) >= USER_LIMIT:
        return "Limit reached"

    f = request.files["code"]
    name = f"{uid}_{f.filename}"
    f.save(os.path.join(BOTS, name))
    return redirect("/dashboard")

# ============ BOT CONTROL ============
@app.route("/start/<f>")
def start_bot(f):
    path = os.path.join(BOTS, f)
    logp = open(os.path.join(LOGS, f + ".log"), "w")
    RUNNING[f] = subprocess.Popen(
        ["python", path],
        stdout=logp,
        stderr=subprocess.STDOUT
    )
    return redirect("/dashboard")

@app.route("/stop/<f>")
def stop_bot(f):
    p = RUNNING.get(f)
    if p:
        p.terminate()
        RUNNING.pop(f, None)
    return redirect("/dashboard")

@app.route("/restart/<f>")
def restart_bot(f):
    stop_bot(f)
    start_bot(f)
    return redirect("/dashboard")

# ============ LOGS ============
@app.route("/logs/<f>")
def logs(f):
    log_file = os.path.join(LOGS, f + ".log")
    data = open(log_file).read() if os.path.exists(log_file) else ""
    return render(f"""
    <div class="card">
      <h3>Logs</h3>
      <pre style="white-space:pre-wrap">{data}</pre>
      <a href="/dashboard"><button class="btn-gray">Close Logs</button></a>
    </div>
    """)

# ============ EDIT CODE ============
@app.route("/edit/<f>", methods=["GET", "POST"])
def edit(f):
    path = os.path.join(BOTS, f)
    if request.method == "POST":
        code = request.form.get("code", "")
        open(path, "w").write(code)
        if f in RUNNING:
            stop_bot(f)
            start_bot(f)
        return redirect("/dashboard")

    code = open(path, "r", errors="ignore").read()
    return render(f"""
    <div class="card">
      <h3>Edit Code</h3>
      <form method="post">
        <textarea name="code">{code}</textarea>
        <button>Save</button>
      </form>
      <a href="/dashboard"><button class="btn-gray">Cancel</button></a>
    </div>
    """)

# ============ DELETE ============
@app.route("/delete/<f>")
def delete(f):
    stop_bot(f)
    try: os.remove(os.path.join(BOTS, f))
    except: pass
    try: os.remove(os.path.join(LOGS, f + ".log"))
    except: pass
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ============ RUN ============
app.run("0.0.0.0", 10000)
