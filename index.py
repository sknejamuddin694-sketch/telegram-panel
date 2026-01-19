import os
import sys
import threading
import subprocess
import zipfile
import random
import hashlib
from datetime import datetime, timedelta
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
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

BOT_TOKEN = "8255116372:AAEHKe0tWHh7rtAparZuA82ZsjPt91KTxFU"
ADMIN_ID = 8465446299

conn = sqlite3.connect(DB_FILE, check_same_thread=False)
cur = conn.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS users (telegram_id INTEGER PRIMARY KEY, password TEXT, verified INTEGER)")
cur.execute("CREATE TABLE IF NOT EXISTS uploads (telegram_id INTEGER, bot_name TEXT, file_size INTEGER, upload_time TEXT)")
conn.commit()

# ---------------- TELEGRAM BOT ----------------
tg = telebot.TeleBot(BOT_TOKEN)

OTP_CACHE = {}
RUNNING_BOTS = {}
PUBLIC_URL = None


def send_otp(tg_id):
    otp = str(random.randint(100000, 999999))
    OTP_CACHE[tg_id] = {"otp": otp, "expires": datetime.now() + timedelta(minutes=10)}
    try:
        tg.send_message(
            tg_id,
            f"🛡️ 𝑲𝑨𝑨𝑳𝑰𝑿 𝑺𝑬𝑪𝑼𝑹𝑰𝑻𝒀 — Your Login OTP: `{otp}` ❗ Don't share this code.",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("OTP send error:", e)


@tg.message_handler(commands=["start"])
def tg_start(msg):
    if PUBLIC_URL:
        # Inline button create karte hain
        keyboard = InlineKeyboardMarkup()
        button = InlineKeyboardButton(text="🌐 𝑶𝒑𝒆𝒏 𝑲𝑨𝑨𝑳𝑰𝑿 𝑷𝒂𝒏𝒆𝒍", url=PUBLIC_URL)
        keyboard.add(button)

        # Message send karte hain button ke saath
        tg.send_message(
    chat_id=msg.chat.id,
    text=(
        "🚀 𝑲𝑨𝑨𝑳𝑰𝑿 𝑷𝒓𝒆𝒎𝒊𝒖𝒎 𝑷𝒂𝒏𝒆𝒍 𝑩𝒐𝒕 𝒊𝒔 𝑶𝒏𝒍𝒊𝒏𝒆\n\n"
        "👇 𝑪𝒍𝒊𝒄𝒌 𝒃𝒆𝒍𝒐𝒘 𝒕𝒐 𝒐𝒑𝒆𝒏 𝒕𝒉𝒆 𝒑𝒂𝒏𝒆𝒍\n\n"
        "🔐 𝑭𝒊𝒓𝒔𝒕-𝑻𝒊𝒎𝒆 𝑳𝒐𝒈𝒊𝒏:\n"
        "• 𝒀𝒐𝒖 𝒎𝒂𝒚 𝒓𝒆𝒄𝒆𝒊𝒗𝒆 𝑶𝑻𝑷 𝒐𝒏 𝒚𝒐𝒖𝒓 𝒇𝒊𝒓𝒔𝒕 𝒍𝒐𝒈𝒊𝒏\n"
        "• 𝑨𝒇𝒕𝒆𝒓 𝒆𝒏𝒕𝒆𝒓𝒊𝒏𝒈 𝑶𝑻𝑷, 𝒕𝒚𝒑𝒆 /𝒂𝒑𝒑𝒓𝒐𝒗𝒆 𝒕𝒐 𝒂𝒄𝒕𝒊𝒗𝒂𝒕𝒆 𝒚𝒐𝒖𝒓 𝒂𝒄𝒄𝒆𝒔𝒔\n\n"
        "⚡ 𝑺𝒆𝒄𝒖𝒓𝒆 • 𝑭𝒂𝒔𝒕 • 𝑷𝒓𝒆𝒎𝒊𝒖𝒎 𝑨𝒄𝒄𝒆𝒔𝒔"
    ),
    reply_markup=keyboard,
    parse_mode="Markdown"
)
    else:
        tg.reply_to(
    msg,
    "🚀 𝑲𝑨𝑨𝑳𝑰𝑿 𝑷𝒓𝒆𝒎𝒊𝒖𝒎 𝑷𝒂𝒏𝒆𝒍 𝑩𝒐𝒕 𝒊𝒔 𝑶𝒏𝒍𝒊𝒏𝒆\n\n"
        "👇 𝑪𝒍𝒊𝒄𝒌 𝒃𝒆𝒍𝒐𝒘 𝒕𝒐 𝒐𝒑𝒆𝒏 𝒕𝒉𝒆 𝒑𝒂𝒏𝒆𝒍\n\n"
        "🔐 𝑭𝒊𝒓𝒔𝒕-𝑻𝒊𝒎𝒆 𝑳𝒐𝒈𝒊𝒏:\n"
        "• 𝒀𝒐𝒖 𝒎𝒂𝒚 𝒓𝒆𝒄𝒆𝒊𝒗𝒆 𝑶𝑻𝑷 𝒐𝒏 𝒚𝒐𝒖𝒓 𝒇𝒊𝒓𝒔𝒕 𝒍𝒐𝒈𝒊𝒏\n"
        "⚡ 𝑺𝒆𝒄𝒖𝒓𝒆 • 𝑭𝒂𝒔𝒕 • 𝑷𝒓𝒆𝒎𝒊𝒖𝒎 𝑨𝒄𝒄𝒆𝒔𝒔"
)


@tg.message_handler(commands=["panel"])
def tg_panel(msg):
    if PUBLIC_URL:
        tg.reply_to(msg, f"🌐 𝑷𝒂𝒏𝒆𝒍 𝑼𝑹𝑳:\n{PUBLIC_URL}")
    else:
        tg.reply_to(msg, "⏳ 𝑷𝒂𝒏𝒆𝒍 𝒊𝒔 𝒔𝒕𝒂𝒓𝒕𝒊𝒏𝒈, 𝒑𝒍𝒆𝒂𝒔𝒆 𝒘𝒂𝒊𝒕...")


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
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700;900&display=swap" rel="stylesheet">
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&display=swap');
    
    * { font-family: 'Inter', sans-serif; }
    .cyber-title { font-family: 'Orbitron', monospace; }
    
    body { 
        background: #000000;
        background-image: 
            radial-gradient(circle at 20% 80%, rgba(120,119,198,0.3) 0%, transparent 50%),
            radial-gradient(circle at 80% 20%, rgba(120,119,198,0.3) 0%, transparent 50%),
            radial-gradient(circle at 40% 40%, rgba(120,119,198,0.2) 0%, transparent 50%);
        background-attachment: fixed;
        color: #e2e8f0; 
        overflow-x: hidden;
        position: relative;
    }
    body::before {
        content: '';
        position: fixed;
        top: 0; left: 0; width: 100%; height: 100%;
        background-image: 
            linear-gradient(45deg, transparent 30%, rgba(59,130,246,0.1) 50%, transparent 70%),
            linear-gradient(-45deg, transparent 30%, rgba(168,85,247,0.1) 50%, transparent 70%);
        background-size: 100px 100px, 100px 100px;
        background-position: 0 0, 50px 50px;
        animation: matrix 20s linear infinite;
        z-index: -1;
        pointer-events: none;
    }
    @keyframes matrix {
        0% { transform: translateX(0) translateY(0); }
        100% { transform: translateX(-100px) translateY(-100px); }
    }
    
    .glass { 
        background: rgba(15, 23, 42, 0.75); 
        backdrop-filter: blur(20px) saturate(1.2); 
        border: 1px solid rgba(100, 116, 139, 0.2); 
        box-shadow: 
            0 25px 45px rgba(0,0,0,0.3),
            0 0 0 1px rgba(255,255,255,0.05),
            inset 0 1px 0 rgba(255,255,255,0.1);
    }
    .glass-morph { 
        background: rgba(30, 58, 138, 0.15); 
        backdrop-filter: blur(25px); 
        border: 1px solid rgba(99, 102, 241, 0.3);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.2);
    }
    
    .neon-glow {
        box-shadow: 
            0 0 5px rgba(59,130,246,0.5),
            0 0 20px rgba(59,130,246,0.3),
            0 0 40px rgba(59,130,246,0.2),
            inset 0 1px 0 rgba(255,255,255,0.5);
    }
    .neon-glow-purple {
        box-shadow: 
            0 0 5px rgba(168,85,247,0.5),
            0 0 20px rgba(168,85,247,0.3),
            0 0 40px rgba(168,85,247,0.2);
    }
    .btn-neon:hover {
        transform: translateY(-2px) scale(1.02);
        box-shadow: 
            0 10px 25px rgba(59,130,246,0.4),
            0 0 30px rgba(59,130,246,0.6),
            0 0 60px rgba(59,130,246,0.4),
            inset 0 1px 0 rgba(255,255,255,0.6);
        animation: btn-shine 0.75s ease-in-out;
    }
    @keyframes btn-shine {
        0% { background-position: -200% 0; }
        100% { background-position: 200% 0; }
    }
    
    .card-float {
        animation: float 6s ease-in-out infinite;
    }
    @keyframes float {
        0%, 100% { transform: translateY(0px) rotateX(0deg); }
        50% { transform: translateY(-10px) rotateX(2deg); }
    }
    
    .status-online { background: linear-gradient(90deg, #10b981, #34d399); box-shadow: 0 0 15px rgba(16,185,129,0.6); }
    .status-offline { background: linear-gradient(90deg, #ef4444, #f87171); box-shadow: 0 0 15px rgba(239,68,68,0.6); }
    
    .code-editor {
        background: rgba(10,15,26,0.9) !important;
        border: 1px solid rgba(59,130,246,0.3) !important;
        box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 30px rgba(59,130,246,0.1) !important;
    }
    .code-editor:focus {
        box-shadow: inset 0 0 20px rgba(0,0,0,0.5), 0 0 40px rgba(59,130,246,0.4) !important;
        border-color: rgba(59,130,246,0.6) !important;
    }
    
    .file-input::-webkit-file-upload-button {
        background: linear-gradient(45deg, #3b82f6, #1d4ed8);
        border: none;
        color: white;
        padding: 0.75rem 1.5rem;
        border-radius: 9999px;
        font-weight: 700;
        cursor: pointer;
        transition: all 0.3s;
    }
    .file-input::-webkit-file-upload-button:hover {
        background: linear-gradient(45deg, #1d4ed8, #1e3a8a);
        transform: scale(1.05);
    }
    
    .particles {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -1;
    }
    .particle {
        position: absolute;
        width: 4px;
        height: 4px;
        background: rgba(59,130,246,0.6);
        border-radius: 50%;
        animation: particle-float 25s linear infinite;
    }
    @keyframes particle-float {
        0% {
            transform: translateY(100vh) rotate(0deg);
            opacity: 0;
        }
        10% {
            opacity: 1;
        }
        90% {
            opacity: 1;
        }
        100% {
            transform: translateY(-100px) rotate(360deg);
            opacity: 0;
        }
    }
    
    @keyframes fadeInUp {
        from { opacity: 0; transform: translateY(30px); }
        to { opacity: 1; transform: translateY(0); }
    }
    .fade-in-up { animation: fadeInUp 0.8s ease-out forwards; }
    
    input, textarea, select {
        background: rgba(30,41,59,0.8) !important;
        border: 1px solid rgba(100,116,139,0.4) !important;
        color: #f8fafc !important;
        transition: all 0.3s ease;
    }
    input:focus, textarea:focus {
        background: rgba(30,41,59,0.95) !important;
        border-color: rgba(59,130,246,0.6) !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.2) !important;
        transform: translateY(-1px);
    }
    
    .gradient-text {
        background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
        background-clip: text;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
</style>
<script>
    // Floating particles
    function createParticles() {
        const particles = document.querySelector('.particles') || document.createElement('div');
        particles.className = 'particles';
        document.body.appendChild(particles);
        
        setInterval(() => {
            const particle = document.createElement('div');
            particle.className = 'particle';
            particle.style.left = Math.random() * 100 + '%';
            particle.style.animationDuration = (Math.random() * 20 + 15) + 's';
            particle.style.animationDelay = Math.random() * 5 + 's';
            particles.appendChild(particle);
            
            setTimeout(() => particle.remove(), 25000);
        }, 300);
    }
    
    // Load particles on page load
    window.addEventListener('load', createParticles);
</script>
"""

# ---------------- HTML TEMPLATES -------------------
LOGIN_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center p-6 relative overflow-hidden">
    <div class="glass w-full max-w-md p-12 rounded-3xl fade-in-up">
        <div class="text-center mb-10 relative">
            <div class="inline-block mb-6 p-4 bg-gradient-to-r from-blue-500 to-purple-600 rounded-3xl neon-glow">
                <h2 class="cyber-title text-5xl font-black gradient-text tracking-[-0.05em]">KAALIX</h2>
            </div>
            <p class="text-slate-400 text-sm font-medium tracking-wider uppercase">Authorized Access Only</p>
        </div>
        <form method="post" class="space-y-6">
            <div class="space-y-2">
                <label class="block text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Telegram ID</label>
                <input name="tgid" required class="w-full px-6 py-4 rounded-2xl outline-none input focus:neon-glow glass-morph transition-all duration-300">
            </div>
            <div class="space-y-2">
                <label class="block text-xs font-bold uppercase tracking-widest text-slate-400 mb-2">Password</label>
                <input name="password" type="password" required class="w-full px-6 py-4 rounded-2xl outline-none input focus:neon-glow glass-morph transition-all duration-300">
            </div>
            <div class="flex items-center justify-between">
                <div class="flex items-center">
                    <input type="checkbox" name="remember" id="rem" class="w-5 h-5 rounded border-slate-600 bg-slate-800 focus:ring-cyan-500">
                    <label for="rem" class="ml-3 text-sm text-slate-400 cursor-pointer select-none">Keep me logged in</label>
                </div>
                <a href="/forgot" class="text-sm text-cyan-400 hover:underline font-bold">Forgot Password?</a>
            </div>
            <button class="w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-black py-5 rounded-2xl transition-all duration-300 btn-neon shadow-2xl relative overflow-hidden">
                <span>ENTER PANEL</span>
            </button>
        </form>
    </div>
</div>
"""

OTP_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center p-6 relative">
    <div class="glass w-full max-w-sm p-12 rounded-3xl text-center fade-in-up glass-morph">
        <div class="inline-flex items-center justify-center w-20 h-20 rounded-full bg-gradient-to-r from-blue-500/20 to-purple-500/20 border-2 border-blue-500/30 mb-8 neon-glow">
            <span class="text-3xl">🔑</span>
        </div>
        <h3 class="text-3xl font-black text-white mb-3 cyber-title">Security Verification</h3>
        <p class="text-slate-400 mb-10 text-sm font-medium">We've sent a 6-digit code to your Telegram.</p>
        <form method="post" class="space-y-6">
            <input name="otp" placeholder="000000" maxlength="6" class="w-full text-center text-4xl font-mono tracking-[0.8em] px-6 py-6 rounded-2xl outline-none focus:neon-glow glass-morph bg-gradient-to-r from-slate-800 to-slate-900">
            <button class="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-900 font-black py-5 rounded-2xl transition-all duration-300 btn-neon shadow-2xl shadow-emerald-500/30">VERIFY CODE</button>
        </form>
        
        <div class="mt-8 pt-8 border-t border-slate-700">
            <a href="https://t.me/YOUR_BOT_USERNAME" target="_blank" 
               class="inline-block w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-500 hover:to-pink-500 text-white font-bold py-4 rounded-2xl transition-all duration-300 btn-neon shadow-2xl">
               🔑 Request OTP on Telegram BOT
            </a>
        </div>
    </div>
</div>
"""

FORGOT_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center p-6 relative">
    <div class="glass w-full max-w-md p-12 rounded-3xl fade-in-up text-center">
        <h3 class="text-3xl font-black text-white mb-6 cyber-title">Forgot Password</h3>
        <p class="text-slate-400 mb-6 text-sm font-medium">Enter your Telegram ID to receive a reset OTP.</p>
        <form method="post" class="space-y-6">
            <input name="tgid" placeholder="Telegram ID" required class="w-full px-6 py-4 rounded-2xl outline-none focus:neon-glow glass-morph">
            <button class="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-900 font-black py-5 rounded-2xl transition-all duration-300 btn-neon shadow-2xl shadow-emerald-500/30">SEND OTP</button>
        </form>
        <div class="mt-6">
            <a href="/" class="text-cyan-400 hover:underline font-bold">Back to Login</a>
        </div>
    </div>
</div>
</body>
</html>
"""

RESET_HTML = BASE_HEAD + """
<div class="min-h-screen flex items-center justify-center p-6 relative">
    <div class="glass w-full max-w-md p-12 rounded-3xl fade-in-up text-center">
        <h3 class="text-3xl font-black text-white mb-6 cyber-title">Reset Password</h3>
        <p class="text-slate-400 mb-6 text-sm font-medium">Enter the OTP sent to Telegram and your new password.</p>
        <form method="post" class="space-y-6">
            <input name="otp" placeholder="Enter OTP" required class="w-full px-6 py-4 rounded-2xl outline-none focus:neon-glow glass-morph">
            <input name="new_password" placeholder="New Password" type="password" required class="w-full px-6 py-4 rounded-2xl outline-none focus:neon-glow glass-morph">
            <button class="w-full bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-900 font-black py-5 rounded-2xl transition-all duration-300 btn-neon shadow-2xl shadow-emerald-500/30">RESET PASSWORD</button>
        </form>
        <div class="mt-6">
            <a href="/" class="text-cyan-400 hover:underline font-bold">Back to Login</a>
        </div>
    </div>
</div>
</body>
</html>
"""

DASH_HTML = BASE_HEAD + """
<div class="max-w-6xl mx-auto p-4 md:p-12 min-h-screen">
    <div class="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
        <div class="space-y-1">
            <h2 class="text-5xl font-black text-white tracking-tighter italic">
                KAALIX <span class="text-transparent bg-clip-text bg-gradient-to-r from-cyan-400 to-blue-500">HOSTING </span>
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
            <h4 class="text-5xl font-black text-emerald-400 mt-3">ONLINE<span class="text-xl"></span></h4>
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
                                <svg class="w-6 h-6 {% if status=='RUNNING' %}text-cyan-400 animate-bot{% else %}text-slate-600{% endif %}"
     fill="none"
     stroke="currentColor"
     viewBox="0 0 24 24">

  <!-- Antenna -->
  <line x1="12" y1="2" x2="12" y2="5" stroke-width="2">
    <animate attributeName="opacity"
             values="1;0.2;1"
             dur="1s"
             repeatCount="indefinite"
             {% if status!='RUNNING' %}begin="indefinite"{% endif %}/>
  </line>

  <!-- Head -->
  <rect x="5" y="6" width="14" height="10" rx="2" stroke-width="2">
    <animateTransform attributeName="transform"
      type="translate"
      values="0 0; 0 -0.5; 0 0"
      dur="1s"
      repeatCount="indefinite"
      {% if status!='RUNNING' %}begin="indefinite"{% endif %}/>
  </rect>

  <!-- Eyes -->
  <circle cx="9" cy="11" r="1" fill="currentColor">
    <animate attributeName="r"
             values="1;0.3;1"
             dur="1.2s"
             repeatCount="indefinite"
             {% if status!='RUNNING' %}begin="indefinite"{% endif %}/>
  </circle>

  <circle cx="15" cy="11" r="1" fill="currentColor">
    <animate attributeName="r"
             values="1;0.3;1"
             dur="1.2s"
             repeatCount="indefinite"
             {% if status!='RUNNING' %}begin="indefinite"{% endif %}/>
  </circle>

  <!-- Body -->
  <line x1="12" y1="16" x2="12" y2="21" stroke-width="2"/>

  <!-- Hands -->
  <line x1="5" y1="14" x2="2" y2="16" stroke-width="2">
    <animateTransform attributeName="transform"
      type="rotate"
      values="0 5 14; 10 5 14; 0 5 14"
      dur="1s"
      repeatCount="indefinite"
      {% if status!='RUNNING' %}begin="indefinite"{% endif %}/>
  </line>

  <line x1="19" y1="14" x2="22" y2="16" stroke-width="2">
    <animateTransform attributeName="transform"
      type="rotate"
      values="0 19 14; -10 19 14; 0 19 14"
      dur="1s"
      repeatCount="indefinite"
      {% if status!='RUNNING' %}begin="indefinite"{% endif %}/>
  </line>

</svg>
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
                    <h3 class="text-3xl font-black mb-3">Deploy New Bot</h3>
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
                        UPLOAD
                    </button>
                </form>
            </div>
        </div>
    </div>
</div>
"""
EDIT_HTML = BASE_HEAD + """
<div class="max-w-6xl mx-auto p-6 md:p-12">
    <div class="flex items-center gap-6 mb-12 fade-in-up">
        <a href="/dashboard" class="w-14 h-14 flex items-center justify-center rounded-2xl bg-slate-900/50 hover:bg-slate-800 text-2xl hover:scale-110 transition-all duration-300 neon-glow">←</a>
        <div>
            <h2 class="text-4xl font-black cyber-title">Edit <span class="gradient-text">{{botname}}</span></h2>
            <p class="text-slate-400 text-sm font-medium mt-1">Make your changes and save</p>
        </div>
    </div>
    <form method='post' class="space-y-8">
        <div class="glass p-8 rounded-3xl glass-morph fade-in-up">
            <label class="block text-lg font-bold mb-6 cyber-title gradient-text">Bot Code Editor</label>
            <textarea name='code' spellcheck="false" class='w-full h-[70vh] p-8 code-editor text-cyan-400 font-mono text-sm rounded-3xl resize-none'>{{ code|e }}</textarea>
        </div>
        <button class='w-full bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-black py-7 rounded-3xl shadow-2xl neon-glow transition-all duration-300 btn-neon text-xl relative overflow-hidden'>
            💾 SAVE & UPDATE BOT
        </button>
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
    if "pending" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        code = request.form.get("otp")
        tgid = session["pending"]
        otp_data = OTP_CACHE.get(tgid)

        if not otp_data:
            return "❌ OTP not found!"
        if datetime.now() > otp_data["expires"]:
            OTP_CACHE.pop(tgid)
            return "❌ OTP expired!"
        if otp_data["otp"] == code:
            OTP_CACHE.pop(tgid)
            cur.execute("UPDATE users SET verified=1 WHERE telegram_id=?", (tgid,))
            conn.commit()
            session.pop("pending")
            session["user"] = tgid
            return redirect(url_for("dashboard"))
        else:
            return "❌ Invalid OTP!"

    return render_template_string(OTP_HTML)


@app.route("/forgot", methods=["GET","POST"])
def forgot():
    if request.method == "POST":
        try:
            tgid = int(request.form.get("tgid"))
            cur.execute("SELECT telegram_id FROM users WHERE telegram_id=?", (tgid,))
            if cur.fetchone():
                # Send OTP with expiry
                otp = str(random.randint(100000, 999999))
                OTP_CACHE[tgid] = {"otp": otp, "expires": datetime.now() + timedelta(minutes=10)}
                try:
                    tg.send_message(
                        tgid,
                        f"🛡️ 𝑲𝑨𝑨𝑳𝑰𝑿 𝑺𝑬𝑪𝑼𝑹𝑰𝑻𝒀 — Your Reset OTP: `{otp}` ❗ Don't share this code.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    print("OTP send error:", e)

                session["reset_pending"] = tgid
                return redirect(url_for("reset_password"))
            else:
                return "❌ Telegram ID not found!"
        except:
            return "❌ Invalid input!"
    return render_template_string(FORGOT_HTML)

@app.route("/reset_password", methods=["GET","POST"])
def reset_password():
    if "reset_pending" not in session:
        return redirect(url_for("forgot"))
    tgid = session["reset_pending"]
    
    if request.method == "POST":
        otp = request.form.get("otp")
        new_pass = request.form.get("new_password")
        
        otp_data = OTP_CACHE.get(tgid)
        if not otp_data:
            return "❌ OTP not found!"
        
        if datetime.now() > otp_data["expires"]:
            OTP_CACHE.pop(tgid)
            return "❌ OTP expired!"
        
        if otp_data["otp"] == otp:
            OTP_CACHE.pop(tgid)  # OTP use hone ke baad delete kar do
            hp = hashlib.sha256(new_pass.encode()).hexdigest()
            cur.execute("UPDATE users SET password=? WHERE telegram_id=?", (hp, tgid))
            conn.commit()
            session.pop("reset_pending")
            return "✅ Password reset successfully! Go back to login."
        else:
            return "❌ Invalid OTP!"
    
    return render_template_string(RESET_HTML)

@app.route("/dashboard")
def dashboard():
    if "user" not in session: return redirect(url_for("login"))
    uid = session["user"]

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

                # AUTO SEND LINK TO ADMIN WITH BUTTON
                try:
                    keyboard = InlineKeyboardMarkup()
                    button = InlineKeyboardButton(text="🌐 Open KAALIX Panel", url=PUBLIC_URL)
                    keyboard.add(button)
                    tg.send_message(
                        ADMIN_ID,
                        "🚀 *KAALIX PANEL LIVE*",
                        parse_mode="Markdown",
                        reply_markup=keyboard
                    )
                except Exception as e:
                    print("Telegram send error:", e)
                break

    threading.Thread(target=start_cloudflare_blocking, daemon=True).start()

    # Start Flask panel
    app.run(host="0.0.0.0", port=PORT, debug=False, use_reloader=False)
