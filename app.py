from flask import Flask, request
import requests
import os

app = Flask(__name__)

BOT_TOKEN = "8080306073:AAHy6IO4j_uResEEN_H2K-PJ2TkPws79mH8"
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

waiting_users = []
active_chats = {}

def send_message(chat_id, text):
    try:
        requests.post(f"{TELEGRAM_URL}/sendMessage", json={'chat_id': chat_id, 'text': text})
        return True
    except:
        return False

@app.route('/')
def home():
    return "🤖 Chattelo Bot is RUNNING!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '').strip()
        
        if text == '/start':
            send_message(chat_id, "👋 Welcome! Use /chat to find partner")
        elif text == '/chat':
            if chat_id in active_chats:
                send_message(chat_id, "❌ Already in chat! Use /stop first")
            elif waiting_users and waiting_users[0] != chat_id:
                partner = waiting_users.pop(0)
                active_chats[chat_id] = partner
                active_chats[partner] = chat_id
                send_message(chat_id, "✅ CONNECTED! Start chatting! 🎉")
                send_message(partner, "✅ CONNECTED! Start chatting! 🎉")
            else:
                if chat_id not in waiting_users:
                    waiting_users.append(chat_id)
                send_message(chat_id, "🔍 Searching for partner...")
        elif text == '/stop':
            if chat_id in active_chats:
                partner = active_chats[chat_id]
                send_message(partner, "❌ Partner left chat")
                del active_chats[partner]
                del active_chats[chat_id]
            send_message(chat_id, "✅ Chat ended")
        else:
            if chat_id in active_chats:
                send_message(active_chats[chat_id], f"💬 {text}")
    
    return "OK"

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
