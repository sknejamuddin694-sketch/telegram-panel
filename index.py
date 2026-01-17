import os, sys, threading, subprocess, sqlite3, hashlib
from flask import Flask, request, redirect, session, render_template_string
from datetime import timedelta
import telebot

# ================== CONFIG ==================
PORT = int(os.environ.get("PORT", 8080))
BOT_TOKEN = os.environ.get("PANEL_BOT_TOKEN")
OWNER_ID = int(os.environ.get("PANEL_ADMIN_ID"))

DATA_DIR = "data"
BOTS_DIR = os.path.join(DATA_DIR, "bots")
os.makedirs(BOTS_DIR, exist_ok=True)

if not BOT_TOKEN or not OWNER_ID:
    raise RuntimeError("Missing PANEL_BOT_TOKEN or PANEL_ADMIN_ID")

# ================== DB ==================
db = sqlite3.connect(os.path.join(DATA_DIR, "panel.db"), check_same_thread=False)
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

# ================== TELEGRAM BOT ==================
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=["start"])
def tg_start(m):
    bot.reply_to(m, "Panel bot online.\nWebsite par login karke /approve bhejo.")

@bot.message_handler(commands=["approve"])
def tg_approve(m):
    uid = m.from_user.id
    cur.execute("UPDATE users SET approved=1 WHERE telegram_id=?", (uid,))
    db.commit()
    bot.reply_to(m, "Approved! Ab website refresh karo.")

# ---- Admin commands (bot) ----
@bot.message_handler(commands=["users"])
def tg_users(m):
    if not is_admin(m.from_user.id): return
    rows = cur.execute("SELECT telegram_id,banned FROM users").fetchall()
    if not rows:
        bot.send_message(m.chat.id, "No users")
        return
    text = "USERS:\n"
    for u,b in rows:
        text += f"{u} | {'BANNED' if b else 'OK'}\n"
    bot.send_message(m.chat.id, text)

@bot.message_handler(commands=["ban"])
def tg_ban(m):
    if not is_admin(m.from_user.id): return
    try:
        uid = int(m.text.split()[1])
        cur.execute("UPDATE users SET banned=1 WHERE telegram_id=?", (uid,))
        db.commit()
        bot.send_message(m.chat.id, f"Banned {uid}")
    except:
        bot.send_message(m.chat.id, "Usage: /ban <chat_id>")

@bot.message_handler(commands=["unban"])
def tg_unban(m):
    if not is_admin(m.from_user.id): return
    try:
        uid = int(m.text.split()[1])
        cur.execute("UPDATE users SET banned=0 WHERE telegram_id=?", (uid,))
        db.commit()
        bot.send_message(m.chat.id, f"Unbanned {uid}")
    except:
        bot.send_message(m.chat.id, "Usage: /unban <chat_id>")

@bot.message_handler(commands=["addadmin"])
def tg_addadmin(m):
    if m.from_user.id != OWNER_ID: return
    try:
        uid = int(m.text.split()[1])
        cur.execute("INSERT OR IGNORE INTO admins VALUES (?)", (uid,))
        db.commit()
        bot.send_message(m.chat.id, f"Admin added: {uid}")
    except:
        bot.send_message(m.chat.id, "Usage: /addadmin <chat_id>")

@bot.message_handler(func=lambda m: True)
def tg_fallback(m):
    bot.reply_to(m, "Website use karo. Login ke baad /approve bhejo.")

def bot_thread():
    bot.infinity_polling(skip_pending=True)

# ================== WEB APP ==================
app = Flask(__name__)
app.secret_key = "panel_secret"
app.permanent_session_lifetime = timedelta(days=7)

LOGIN_HTML = """
<h2>Login</h2>
{% if session.get('need_approve') %}
<p style="color:red">Telegram par /approve bhejo, phir refresh.</p>
{% endif %}
<form method="post">
<input name="tgid" placeholder="Telegram ID" required><br>
<input type="password" name="password" placeholder="Password" required><br>
<button>Login</button>
</form>
"""

DASH_HTML = """
<h2>Dashboard {{uid}}</h2>
<form method="post" action="/upload" enctype="multipart/form-data">
<input type="file" name="code" required>
<button>Upload (.py only)</button>
</form>
<ul>
{% for f in files %}
<li>{{f}}</li>
{% endfor %}
</ul>
<a href="/logout">Logout</a>
"""

@app.route("/", methods=["GET","POST"])
def login():
    # safe redirect (no loop)
    if session.get("user") and not session.get("need_approve"):
        return redirect("/dashboard")

    if request.method == "POST":
        uid = int(request.form["tgid"])
        pw = hashlib.sha256(request.form["password"].encode()).hexdigest()

        row = cur.execute(
            "SELECT password,banned FROM users WHERE telegram_id=?", (uid,)
        ).fetchone()

        if row and row[1]:
            return "You are banned"

        if not row:
            cur.execute("INSERT INTO users VALUES (?,?,0,0)", (uid, pw))
            db.commit()

        if (not row) or row[0] == pw:
            session["user"] = uid
            # owner/admin bypass approval
            if not is_admin(uid):
                session["need_approve"] = True
            return redirect("/dashboard")

    return render_template_string(LOGIN_HTML)

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    uid = session["user"]

    # approval check (non-admin only)
    if not is_admin(uid):
        ok = cur.execute(
            "SELECT approved FROM users WHERE telegram_id=?", (uid,)
        ).fetchone()[0]
        if not ok:
            session["need_approve"] = True
            return redirect("/")

    session.pop("need_approve", None)

    files = [f for f in os.listdir(BOTS_DIR) if f.startswith(f"{uid}_")]
    return render_template_string(DASH_HTML, uid=uid, files=files)

@app.route("/upload", methods=["POST"])
def upload():
    uid = session.get("user")
    if not uid:
        return redirect("/")

    file = request.files.get("code")
    if not file:
        return "No file"

    # ONLY PYTHON
    if not file.filename.lower().endswith(".py"):
        return "Only .py files allowed"

    # limit: normal user = 3
    user_files = [f for f in os.listdir(BOTS_DIR) if f.startswith(f"{uid}_")]
    if (not is_admin(uid)) and len(user_files) >= 3:
        return "Upload limit reached (3 Python files)"

    path = os.path.join(BOTS_DIR, f"{uid}_{file.filename}")
    file.save(path)

    # AUTO RUN
    subprocess.Popen([sys.executable, path])

    return redirect("/dashboard")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================== START ==================
if __name__ == "__main__":
    threading.Thread(target=bot_thread, daemon=True).start()
    app.run("0.0.0.0", PORT)
