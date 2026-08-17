import json
import os
import threading
import time
import urllib.request
from datetime import datetime

from flask import Flask, request, jsonify

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG = json.load(open(os.path.join(BASE_DIR, "config.json")))

INSTANCE = os.environ.get("GREEN_INSTANCE", "")
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


def now_time():
    return datetime.now().strftime("%H:%M")


def is_open():
    t = now_time()
    return CONFIG["OPEN_TIME"] <= t <= CONFIG["CLOSE_TIME"]


def welcome_text():
    return CONFIG["WELCOME"].replace("SHOPNAME", CONFIG["SHOP_NAME"])


def catalog_text():
    lines = [f"*{CONFIG['SHOP_NAME']} - Products & Prices:*", ""]
    for i, item in enumerate(CONFIG["CATALOG"], 1):
        lines.append(f"{i}. {item['name']} - {item['price']}")
    lines.append("")
    lines.append("Order karna hai? Item ka number reply karo. Example: '2 milk'")
    return "\n".join(lines)


def find_price(text):
    low = text.lower()
    best = None
    for item in CONFIG["CATALOG"]:
        for part in item["name"].lower().split():
            if part in low:
                best = item
                break
        if best:
            break
    return best


def reply_for(text):
    low = text.strip().lower()

    if low in ("1", "products", "product", "price", "prices", "rate", "rates", "menu", "catalog"):
        return catalog_text()

    if low in ("2", "order", "order karna", "order karni"):
        return "Batao kya chahiye? Item ka naam aur quantity likho.\nExample: '2 atta, 1 milk'"

    if low in ("3", "delivery"):
        return CONFIG["DELIVERY"]

    if low in ("4", "timing", "timings", "time", "address", "location"):
        return (
            f"*{CONFIG['SHOP_NAME']}*\n"
            f"Timing: {CONFIG['OPEN_TIME']} - {CONFIG['CLOSE_TIME']} (Mon-Sun)\n"
            f"Address: {CONFIG['ADDRESS']}\n"
            f"Contact: {CONFIG['CONTACT']}"
        )

    if low in ("5", "payment", "upi", "payment kaise"):
        return f"Payment UPI: *{CONFIG['UPI_ID']}*\nCash bhi available hai.\nKuch aur chahiye?"

    item = find_price(low)
    if item:
        return f"{item['name']} ka price: *{item['price']}*\nOrder karna ho to reply karo 'order {item['name'].lower()}'"

    if any(k in low for k in CONFIG["KEYWORDS_TIMING"]):
        return (
            f"Timing: {CONFIG['OPEN_TIME']} - {CONFIG['CLOSE_TIME']} (Mon-Sun)\n"
            f"Address: {CONFIG['ADDRESS']}"
        )

    if any(k in low for k in CONFIG["KEYWORDS_PAYMENT"]):
        return f"Payment UPI: *{CONFIG['UPI_ID']}*\nCash bhi available hai."

    if any(k in low for k in CONFIG["KEYWORDS_DELIVERY"]):
        return CONFIG["DELIVERY"]

    if any(k in low for k in CONFIG["KEYWORDS_ORDER"]):
        return (
            "Order confirm karte hain.\n"
            "Items + quantity batao, aur apna address dena (agar delivery chahiye).\n"
            "Example: '2 milk, 1 bread - near bus stand'"
        )

    if any(k in low for k in CONFIG["KEYWORDS_PRICE"]):
        return catalog_text()

    return (
        "Samajh nahi paya. Options:\n"
        "1. Products & Price\n"
        "2. Order karna\n"
        "3. Delivery\n"
        "4. Timing & Address\n"
        "5. Payment (UPI)"
    )


def handle_message(chat_id, text):
    with conversation_lock:
        state = conversation.get(chat_id)
        now = time.time()
        if not state or now - state["ts"] > TIMEOUT_SECONDS:
            conversation[chat_id] = {"step": "idle", "ts": now}
            state = conversation[chat_id]

    low = text.strip().lower()
    step = state["step"]

    if step == "idle":
        reply = reply_for(text)
        if reply.startswith("Order confirm karte"):
            state["step"] = "collecting"
            state["ts"] = time.time()
        send_message(chat_id, reply)
        return

    if step == "collecting":
        state["step"] = "done"
        state["ts"] = time.time()
        try:
            with open(CONFIG["ORDER_STORAGE"], "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} | {chat_id} | {text}\n")
        except Exception as e:
            print("order save failed:", e)
        send_message(
            chat_id,
            "Order received! ✅\n"
            f"*Your order:* {text}\n"
            f"Delivery: {CONFIG['DELIVERY']}\n"
            f"Payment: {CONFIG['UPI_ID']}\n"
            "Shop aate hi confirm karke time bataenge. Dhanyawad! 🙏",
        )
        return

    if step == "done":
        send_message(chat_id, reply_for(text))
        return


@app.route("/", methods=["GET"])
def index():
    return "WhatsApp Bot is running!", 200


@app.route("/green-webhook", methods=["POST"])
def green_webhook():
    data = request.get_json(force=True)
    try:
        if data.get("typeWebhook") != "incomingMessageReceived":
            return jsonify({"status": "ignored"}), 200
        sender = data.get("senderData", {}).get("chatId", "")
        msg_data = data.get("messageData", {})
        if msg_data.get("typeMessage") != "textMessage":
            send_message(sender, "Sirf text messages support hain abhi. Apna order text mein likhein.")
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