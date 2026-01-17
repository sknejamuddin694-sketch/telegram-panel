import os, subprocess, time
from flask import Flask, request, session, redirect, render_template_string
import telebot
from telebot.types import Update

# ================= CONFIG =================
BOT_TOKEN = "YOUR_PANEL_BOT_TOKEN"
OWNER_ID = "8465446299"
BASE_URL = "https://your-app.onrender.com"
APPROVE_BOT = "https://t.me/Mr_rocky_99_bot"

USER_LIMIT = 3
DATA="data"; BOTS=f"{DATA}/bots"; LOGS=f"{DATA}/logs"
os.makedirs(BOTS,exist_ok=True); os.makedirs(LOGS,exist_ok=True)

RUNNING = {}
APPROVED = set()

app = Flask(__name__)
app.secret_key="craka-secure"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ================= TELEGRAM =================
@bot.message_handler(commands=["start"])
def tg_start(m):
    bot.send_message(m.chat.id,"Panel connected ✅\nApprove ke liye /approve")

@bot.message_handler(commands=["approve"])
def tg_approve(m):
    APPROVED.add(str(m.chat.id))
    bot.send_message(m.chat.id,"✅ Approved! Website refresh karo")

@app.route("/telegram",methods=["POST"])
def telegram():
    update = Update.de_json(request.data.decode(), bot)
    bot.process_new_updates([update])
    return "OK"

bot.remove_webhook()
bot.set_webhook(url=f"{BASE_URL}/telegram")

# ================= UI =================
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name=viewport content="width=device-width,initial-scale=1">
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
 position:fixed;inset:0;
 background:url('https://i.imgur.com/NM8ZC2B.png');
 opacity:.25;
 animation:snow 25s linear infinite;
}
@keyframes snow{from{background-position:0 0}to{background-position:0 1200px}}
.card{
 background:rgba(255,255,255,.08);
 padding:20px;border-radius:14px;
 width:320px;margin:12vh auto;
}
input,textarea,button{
 width:100%;padding:10px;
 border-radius:8px;border:none;margin:6px 0;
 font-family:monospace;
}
textarea{height:260px}
button{background:#8b5cf6;color:white;font-weight:800}
.btn-red{background:#ef4444}
.btn-gray{background:#6b7280}
.footer{
 position:fixed;bottom:10px;width:100%;
 text-align:center;font-size:18px;font-weight:900
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
    return render_template_string(BASE_HTML,body=body)

# ================= LOGIN =================
@app.route("/",methods=["GET","POST"])
def login():
    if request.method=="POST":
        uid=request.form["tgid"]
        if uid not in APPROVED:
            return render(f"""
            <div class=card>
            <h3>Approval Required</h3>
            <a href="{APPROVE_BOT}" target=_blank>
            <button>Approve Now</button></a>
            </div>
            """)
        session["uid"]=uid
        return redirect("/dashboard")

    return render("""
    <div class=card>
    <h3>Sign In</h3>
    <form method=post>
    <input name=tgid placeholder="Telegram ID">
    <input type=password placeholder="Password">
    <button>Sign In</button>
    </form>
    </div>
    """)

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    uid=session.get("uid")
    if not uid: return redirect("/")

    files=[f for f in os.listdir(BOTS) if f.startswith(uid+"_")]
    limit=999 if uid==OWNER_ID else USER_LIMIT

    body=f"<div class=card><h3>Your Bots ({len(files)}/{limit})</h3>"

    for i,f in enumerate(files,1):
        run=f in RUNNING
        body+=f"""
        <hr><b>{i}. {f}</b><br>
        {'' if run else f'<a href=/start/{f}><button>Start</button></a>'}
        {f'<a href=/stop/{f}><button class=btn-red>Stop</button></a>' if run else ''}
        {f'<a href=/restart/{f}><button>Restart</button></a>' if run else ''}
        <a href=/edit/{f}><button>Edit</button></a>
        <a href=/logs/{f}><button class=btn-gray>Logs</button></a>
        <a href=/delete/{f}><button class=btn-red>Delete</button></a>
        """

    body+=f"""
    <form method=post action=/upload enctype=multipart/form-data>
    <input type=file name=code required>
    <button>Upload</button></form>
    <a href=/logout><button class=btn-gray>Logout</button></a>
    </div>
    """
    return render(body)

# ================= UPLOAD =================
@app.route("/upload",methods=["POST"])
def upload():
    uid=session.get("uid")
    files=[f for f in os.listdir(BOTS) if f.startswith(uid+"_")]
    if uid!=OWNER_ID and len(files)>=USER_LIMIT:
        return "Limit reached"
    f=request.files["code"]
    name=f"{uid}_{f.filename}"
    f.save(f"{BOTS}/{name}")
    return redirect("/dashboard")

# ================= BOT CONTROL =================
@app.route("/start/<f>")
def start_bot(f):
    RUNNING[f]=subprocess.Popen(
        ["python",f"{BOTS}/{f}"],
        stdout=open(f"{LOGS}/{f}.log","w"),
        stderr=subprocess.STDOUT
    )
    return redirect("/dashboard")

@app.route("/stop/<f>")
def stop_bot(f):
    if f in RUNNING:
        RUNNING[f].terminate()
        RUNNING.pop(f)
    return redirect("/dashboard")

@app.route("/restart/<f>")
def restart(f):
    stop_bot(f); start_bot(f)
    return redirect("/dashboard")

# ================= LOGS =================
@app.route("/logs/<f>")
def logs(f):
    data=open(f"{LOGS}/{f}.log","r").read() if os.path.exists(f"{LOGS}/{f}.log") else ""
    return render(f"""
    <div class=card>
    <h3>Logs</h3>
    <pre>{data}</pre>
    <a href=/dashboard><button class=btn-gray>Close Logs</button></a>
    </div>
    """)

# ================= EDIT CODE =================
@app.route("/edit/<f>",methods=["GET","POST"])
def edit(f):
    path=f"{BOTS}/{f}"
    if request.method=="POST":
        code=request.form["code"]
        open(path,"w").write(code)
        if f in RUNNING:
            stop_bot(f); start_bot(f)
        return redirect("/dashboard")

    code=open(path,"r",errors="ignore").read()
    return render(f"""
    <div class=card>
    <h3>Edit Code</h3>
    <form method=post>
    <textarea name=code>{code}</textarea>
    <button>Save</button>
    </form>
    <a href=/dashboard><button class=btn-gray>Cancel</button></a>
    </div>
    """)

# ================= DELETE =================
@app.route("/delete/<f>")
def delete(f):
    stop_bot(f)
    try: os.remove(f"{BOTS}/{f}")
    except: pass
    try: os.remove(f"{LOGS}/{f}.log")
    except: pass
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================
app.run("0.0.0.0",10000)
