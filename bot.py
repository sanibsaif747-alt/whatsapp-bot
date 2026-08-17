import json
import os
import random
import threading
import time
import urllib.request
from datetime import datetime

from flask import Flask, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = json.load(open(os.path.join(BASE_DIR, "config.json")))

INSTANCE = os.environ.get("GREEN_INSTANCE", "710722712388")
TOKEN = os.environ.get("GREEN_TOKEN", "")
API_BASE = "https://api.green-api.com"

app = Flask(__name__)

conversation = {}
conversation_lock = threading.Lock()
TIMEOUT_SECONDS = 1800


def send_message(chat_id, text):
    url = f"{API_BASE}/waInstance{INSTANCE}/sendMessage/{TOKEN}"
    payload = {"chatId": chat_id, "message": text}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status
    except Exception as e:
        print("send failed:", e)
        return 0


def welcome_text():
    return CONFIG["WELCOME"]


def reply_for(text):
    low = text.strip().lower()

    if low in ("1", "chat", "chat karein", "hang out"):
        return random.choice(CONFIG["CHAT_LINES"])

    if low in ("2", "idea", "ideas", "suggest", "content"):
        return random.choice(CONFIG["IDEA_LINES"])

    if low in ("3", "code", "coding", "help code"):
        return (
            "NIB·BOT: code mode on 🤖\n"
            "Tell me what you need:\n"
            "✦ 'python loop' — loop examples\n"
            "✦ 'js function' — JS snippet\n"
            "✦ 'app idea' — app concepts\n"
            "✦ or paste your error, I'll decode it."
        )

    if low in ("4", "mood", "motivate", "motivation", "vibe"):
        return random.choice(CONFIG["MOTIVATION_LINES"])

    if low in ("5", "links", "social", "instagram", "about"):
        return CONFIG["OWNER_BIO"]

    if low.startswith("python") or "python" in low:
        return (
            "NIB·BOT: Python snippet 🐍\n"
            "```python\n"
            "for i in range(5):\n"
            "    print('vibe', i)\n"
            "```\n"
            "More? type 'python loop' or 'python list'"
        )

    if low.startswith("js") or "javascript" in low:
        return (
            "NIB·BOT: JS snippet ⚡\n"
            "```javascript\n"
            "const vibes = ['aesthetic', 'code', 'glow'];\n"
            "vibes.forEach(v => console.log(v));\n"
            "```"
        )

    if "error" in low or "bug" in low:
        return (
            "NIB·BOT: debugging mode 🐛\n"
            "1. Read the last line of the error — it tells you where.\n"
            "2. Check variable names (typo = 90% of bugs).\n"
            "3. Print the value — see what's actually there.\n"
            "Paste your error here, I'll help decode it."
        )

    if any(k in low for k in CONFIG["KEYWORDS_MOOD"]):
        return random.choice(CONFIG["MOTIVATION_LINES"])

    if any(k in low for k in CONFIG["KEYWORDS_IDEA"]):
        return random.choice(CONFIG["IDEA_LINES"])

    if any(k in low for k in CONFIG["KEYWORDS_CODE"]):
        return (
            "NIB·BOT: I know a thing or two 🤖\n"
            "Ask me: python loop, js function, html page, error help."
        )

    if any(k in low for k in CONFIG["KEYWORDS_LINKS"]):
        return CONFIG["OWNER_BIO"]

    if any(k in low for k in CONFIG["KEYWORDS_CHAT"]):
        return random.choice(CONFIG["CHAT_LINES"])

    if "?" in text or "kya" in low or "what" in low or "kaise" in low:
        return (
            "NIB·BOT: good question ✦\n"
            "I'm a simple bot — chat, ideas, code, vibes.\n"
            "Type 'menu' to see what I can do."
        )

    return (
        "NIB·BOT: I vibe with that ✦\n"
        "Type 'menu' for options, or just keep talking."
    )


def handle_message(chat_id, text):
    with conversation_lock:
        state = conversation.get(chat_id)
        now = time.time()
        if not state or now - state["ts"] > TIMEOUT_SECONDS:
            conversation[chat_id] = {"step": "idle", "ts": now}
            state = conversation[chat_id]

    low = text.strip().lower()

    if low in ("menu", "help", "options", "start", "hi", "hello", "hey", "yo"):
        send_message(chat_id, welcome_text())
        return

    if state["step"] == "idle":
        state["ts"] = time.time()
        send_message(chat_id, reply_for(text))
        return

    send_message(chat_id, reply_for(text))


@app.route("/", methods=["GET"])
def index():
    return "NIB·BOT is running!", 200


@app.route("/green-webhook", methods=["POST"])
def green_webhook():
    data = request.get_json(force=True)
    try:
        if data.get("typeWebhook") != "incomingMessageReceived":
            return jsonify({"status": "ignored"}), 200
        sender = data.get("senderData", {}).get("chatId", "")
        msg_data = data.get("messageData", {})
        if msg_data.get("typeMessage") != "textMessage":
            send_message(sender, "NIB·BOT: text only for now ✦ send me words.")
            return jsonify({"status": "received"}), 200
        text = msg_data.get("textMessageData", {}).get("textMessage", "")
        if not sender or not text:
            return jsonify({"status": "ignored"}), 200
        threading.Thread(target=handle_message, args=(sender, text), daemon=True).start()
    except Exception as e:
        print("webhook error:", e)
    return jsonify({"status": "received"}), 200


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)