# ================= TELEGRAM TERMUX CONTROLLER =================
# Single file | No panel | Bot based | Editor link only
# ===============================================================

import os, subprocess, threading, uuid
from flask import Flask, request, render_template_string
import telebot

# ---------------- CONFIG ----------------
BOT_TOKEN = "8440660703:AAHppsz0_NZzbyxU91vHM5W54CD_Xy_G5WA"
ADMIN_ID = 8465446299
BASE_DIR = os.getcwd()
PORT = 9890

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

edit_sessions = {}
processes = {}

# ---------------- UTILS ----------------
def run_cmd(cmd, chat_id):
    def task():
        p = subprocess.Popen(
            cmd,
            shell=True,
            cwd=BASE_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT
        )
        processes[chat_id] = p
        for line in iter(p.stdout.readline, b''):
            bot.send_message(chat_id, line.decode(errors="ignore"))
    threading.Thread(target=task).start()

# ---------------- TELEGRAM ----------------
@bot.message_handler(commands=["start"])
def start(m):
    bot.send_message(
        m.chat.id,
        "🥱 *TERMUX BOT READY*\n\n"
        "`ls`\n"
        "`python bot.py`\n"
        "`nano test.py`\n\n"
        "Sab command yahin likho",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: True)
def shell(m):
    cmd = m.text.strip()

    # NANO INTERCEPT
    if cmd.startswith("nano "):
        filename = cmd.split(" ", 1)[1]
        file_path = os.path.join(BASE_DIR, filename)
        if not os.path.exists(file_path):
            open(file_path, "w").close()

        sid = str(uuid.uuid4())
        edit_sessions[sid] = file_path
        link = f"http://localhost:{PORT}/edit/{sid}"

        bot.send_message(
            m.chat.id,
            f"✏️ EDIT MODE\n\nOpen link:\n{link}\n\nSave kar ke wapas aao",
        )
        return

    # LOGS
    if cmd == "logs":
        bot.send_message(m.chat.id, "📄 Logs auto commands ke sath aa rahe hain")
        return

    # STOP
    if cmd == "stop":
        p = processes.get(m.chat.id)
        if p:
            p.terminate()
            bot.send_message(m.chat.id, "🛑 Process stopped")
        return

    # NORMAL COMMAND
    bot.send_message(m.chat.id, f"$ {cmd}")
    run_cmd(cmd, m.chat.id)

# ---------------- EDITOR ----------------
@app.route("/edit/<sid>", methods=["GET", "POST"])
def edit(sid):
    if sid not in edit_sessions:
        return "Invalid session"

    file = edit_sessions[sid]

    if request.method == "POST":
        with open(file, "w") as f:
            f.write(request.form["code"])
        return "<h2>✅ Saved! You can close this page.</h2>"

    code = open(file).read()
    return render_template_string("""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Code Editor</title>
<link href="https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;700&display=swap" rel="stylesheet">
<style>
    * {
        margin: 0;
        padding: 0;
        box-sizing: border-box;
    }

    body {
        background: #0d1117;
        color: #c9d1d9;
        font-family: 'Fira Code', monospace;
        display: flex;
        flex-direction: column;
        height: 100vh;
        padding: 20px;
    }

    header {
        text-align: center;
        margin-bottom: 15px;
    }

    header h1 {
        color: #58a6ff;
        font-weight: 700;
    }

    form {
        flex: 1;
        display: flex;
        flex-direction: column;
    }

    textarea {
        flex: 1;
        width: 100%;
        padding: 15px;
        font-size: 14px;
        border-radius: 10px;
        border: none;
        background: #161b22;
        color: #c9d1d9;
        resize: none;
        outline: none;
        box-shadow: inset 0 0 10px rgba(0,255,0,0.1);
        transition: all 0.2s;
    }

    textarea:focus {
        box-shadow: inset 0 0 15px rgba(88,166,255,0.5);
        background: #0d1117;
    }

    button {
        margin-top: 15px;
        padding: 12px;
        background: #238636;
        color: #fff;
        border: none;
        border-radius: 10px;
        font-weight: 600;
        font-size: 16px;
        cursor: pointer;
        transition: all 0.2s;
    }

    button:hover {
        background: #2ea043;
        transform: scale(1.02);
    }

    @media (max-width: 600px) {
        textarea {
            font-size: 13px;
        }

        button {
            font-size: 14px;
        }
    }
</style>
</head>
<body>
<header>
    <h1>🖋️ Code Editor</h1>
</header>
<form method="post">
    <textarea name="code">{{code}}</textarea>
    <button type="submit">SAVE</button>
</form>
</body>
</html>
""", code=code)

# ---------------- START ----------------
def flask_run():
    app.run("localhost", PORT)

threading.Thread(target=flask_run, daemon=True).start()
bot.infinity_polling()
