import os, threading, subprocess, time, signal
from flask import Flask, request, session, redirect, render_template_string, send_file
import telebot

# ================= CONFIG =================
BOT_TOKEN = "PASTE_YOUR_PANEL_BOT_TOKEN"
APPROVE_BOT_LINK = "https://t.me/Mr_rocky_99_bot"
OWNER_IDS = ["8465446299"]   # owner chat ids (unlimited)
USER_LIMIT = 3

BASE = "data"
BOTS = f"{BASE}/bots"
LOGS = f"{BASE}/logs"

os.makedirs(BOTS, exist_ok=True)
os.makedirs(LOGS, exist_ok=True)

RUNNING = {}

app = Flask(__name__)
app.secret_key = "craka-secure-panel"

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)

# ================= BOT =================
@bot.message_handler(commands=["start"])
def start(m):
    bot.reply_to(m, "Panel connected ✅")

@bot.message_handler(commands=["approve"])
def approve(m):
    session_key = f"approve_{m.chat.id}"
    open(session_key, "w").close()
    bot.reply_to(m, "Approved ✅ अब website refresh करो")

def bot_thread():
    while True:
        try:
            bot.infinity_polling(skip_pending=True)
        except:
            time.sleep(5)

threading.Thread(target=bot_thread, daemon=True).start()

# ================= UI BASE =================
BASE_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta name=viewport content="width=device-width, initial-scale=1">
<title>Python Bot Hosting</title>
<style>
body{
 margin:0;
 font-family:Arial;
 background:linear-gradient(135deg,#2b1055,#000);
 color:white;
 overflow:hidden;
}
.snow{position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;}
.card{
 background:rgba(255,255,255,0.08);
 padding:20px;
 border-radius:14px;
 width:300px;
 margin:auto;
 margin-top:15vh;
 box-shadow:0 0 20px rgba(0,0,0,.5);
}
input,button{
 width:100%;
 padding:10px;
 margin:6px 0;
 border-radius:8px;
 border:none;
}
button{background:#8b5cf6;color:white;font-weight:bold}
.btn-red{background:#ef4444}
.btn-gray{background:#6b7280}
a{text-decoration:none}
.footer{
 position:fixed;
 bottom:10px;
 width:100%;
 text-align:center;
 font-size:13px;
 opacity:.7;
}
</style>
</head>
<body>

<canvas class="snow"></canvas>

{{body|safe}}

<div class="footer">
Developed by 
<span style="cursor:pointer;text-decoration:underline"
onclick="window.open('https://t.me/DM_CRAKA_OWNER_BOT','_blank')">
C̶R̶A̶K̶A̶
</span>
</div>

<script>
const c=document.querySelector('.snow'),x=c.getContext('2d');
c.width=innerWidth;c.height=innerHeight;
let s=[];
for(let i=0;i<80;i++)s.push({x:Math.random()*c.width,y:Math.random()*c.height,r:Math.random()*2+1});
function draw(){
x.clearRect(0,0,c.width,c.height);
x.fillStyle='rgba(255,255,255,.6)';
s.forEach(f=>{
x.beginPath();x.arc(f.x,f.y,f.r,0,Math.PI*2);x.fill();
f.y+=.5;if(f.y>c.height)f.y=0;
});
requestAnimationFrame(draw);
}
draw();
</script>

</body>
</html>
"""

# ================= ROUTES =================
@app.route("/", methods=["GET","POST"])
def login():
    if request.method=="POST":
        uid=request.form["tgid"]
        pwd=request.form["password"]

        if not os.path.exists(f"approve_{uid}"):
            session["need"]=True
            return redirect("/")
        session["user"]=uid
        return redirect("/dashboard")

    msg=""
    if session.pop("need",None):
        msg="<p style='color:#ffaaaa'>Telegram me /approve bhejo</p>"
    body=f"""
    <div class=card>
    <h3>Sign In</h3>{msg}
    <form method=post>
    <input name=tgid placeholder="Telegram ID">
    <input type=password name=password placeholder="Password">
    <button>Sign In</button>
    </form>
    </div>
    """
    return render_template_string(BASE_HTML,body=body)

@app.route("/dashboard")
def dash():
    uid=session.get("user")
    if not uid: return redirect("/")

    files=[f for f in os.listdir(BOTS) if f.startswith(uid+"_")]
    limit=999 if uid in OWNER_IDS else USER_LIMIT

    popup=""
    if session.pop("uploaded",None):
        popup="<script>alert('Code uploaded successfully');</script>"

    body=popup+f"<div class=card><h3>Your Bots ({len(files)}/{limit})</h3>"

    for i,f in enumerate(files,1):
        run=f in RUNNING
        body+=f"""
        <hr>
        <b>{i}. {f}</b><br>
        {'' if run else f'<a href=/start/{f}><button>Start</button></a>'}
        {f'<a href=/stop/{f}><button class=btn-red>Stop</button></a>' if run else ''}
        {f'<a href=/restart/{f}><button>Restart</button></a>' if run else ''}
        <a href=/logs/{f}><button class=btn-gray>Logs</button></a>
        """
    body+="""
    <form method=post action=/upload enctype=multipart/form-data>
    <input type=file name=code>
    <button>Upload</button>
    </form>

    <form method=post action=/delete>
    <input name=num placeholder="Delete code number">
    <button class=btn-red>Delete</button>
    </form>

    <a href=/logout><button class=btn-gray>Logout</button></a>
    </div>
    """
    return render_template_string(BASE_HTML,body=body)

@app.route("/upload",methods=["POST"])
def upload():
    uid=session.get("user")
    if not uid: return redirect("/")
    files=[f for f in os.listdir(BOTS) if f.startswith(uid+"_")]
    if uid not in OWNER_IDS and len(files)>=USER_LIMIT:
        return "Limit reached"
    f=request.files["code"]
    name=f"{uid}_{f.filename}"
    f.save(f"{BOTS}/{name}")
    session["uploaded"]=True
    return redirect("/dashboard")

@app.route("/start/<f>")
def start_bot(f):
    p=subprocess.Popen(["python",f"{BOTS}/{f}"],
        stdout=open(f"{LOGS}/{f}.log","w"),
        stderr=subprocess.STDOUT)
    RUNNING[f]=p
    return redirect("/dashboard")

@app.route("/stop/<f>")
def stop_bot(f):
    p=RUNNING.get(f)
    if p:
        p.terminate()
        RUNNING.pop(f)
    return redirect("/dashboard")

@app.route("/restart/<f>")
def restart(f):
    stop_bot(f); start_bot(f); return redirect("/dashboard")

@app.route("/logs/<f>")
def logs(f):
    return send_file(f"{LOGS}/{f}.log")

@app.route("/delete",methods=["POST"])
def delete():
    uid=session.get("user")
    n=int(request.form["num"])-1
    files=[f for f in os.listdir(BOTS) if f.startswith(uid+"_")]
    if 0<=n<len(files):
        f=files[n]
        stop_bot(f)
        os.remove(f"{BOTS}/{f}")
        try: os.remove(f"{LOGS}/{f}.log")
        except: pass
    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= RUN =================
app.run(host="0.0.0.0",port=10000)
