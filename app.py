from flask import Flask, request
import requests
import os
import json

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', "8080306073:AAHy6IO4j_uResEEN_H2K-PJ2TkPws79mH8")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

waiting_users = []
active_chats = {}

def send_message(chat_id, text):
    try:
        response = requests.post(
            f"{TELEGRAM_URL}/sendMessage", 
            json={'chat_id': chat_id, 'text': text}
        )
        return True
    except:
        return False

def send_message_with_buttons(chat_id, text):
    """Send message with 3 buttons"""
    buttons = [
        [{"text": "🔍 Find Partner", "callback_data": "find"}],
        [{"text": "🛑 Stop Chat", "callback_data": "stop"}],
        [{"text": "📊 My Stats", "callback_data": "stats"}]
    ]
    
    keyboard = {"inline_keyboard": buttons}
    
    payload = {
        'chat_id': chat_id,
        'text': text,
        'reply_markup': json.dumps(keyboard)
    }
    
    try:
        requests.post(f"{TELEGRAM_URL}/sendMessage", json=payload)
        return True
    except:
        return False

@app.route('/')
def home():
    return "🤖 Bot with BUTTONS is RUNNING!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    # Handle button clicks
    if 'callback_query' in data:
        callback = data['callback_query']
        chat_id = callback['message']['chat']['id']
        button_data = callback['data']
        
        if button_data == 'find':
            handle_chat(chat_id)
        elif button_data == 'stop':
            handle_stop(chat_id)
        elif button_data == 'stats':
            handle_stats(chat_id)
        
        # Tell Telegram we received the button click
        requests.post(f"{TELEGRAM_URL}/answerCallbackQuery", 
                     json={'callback_query_id': callback['id']})
        return "OK"
    
    # Handle normal messages
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        text = data['message'].get('text', '').strip()
        
        if text == '/start':
            # Send welcome message WITH BUTTONS
            welcome_text = "👋 Welcome to Chattelo!\n\nClick buttons below:"
            send_message_with_buttons(chat_id, welcome_text)
            
        elif text == '/chat':
            handle_chat(chat_id)
        elif text == '/stop':
            handle_stop(chat_id)
        else:
            if chat_id in active_chats:
                send_message(active_chats[chat_id], f"💬 {text}")
            else:
                send_message(chat_id, "❌ Use /chat first or click 'Find Partner' button")
    
    return "OK"

def handle_chat(chat_id):
    if chat_id in active_chats:
        send_message(chat_id, "❌ Already in chat! Click 'Stop Chat' first")
        return
        
    if waiting_users and waiting_users[0] != chat_id:
        partner = waiting_users.pop(0)
        active_chats[chat_id] = partner
        active_chats[partner] = chat_id
        send_message(chat_id, "✅ CONNECTED! Start chatting! 🎉")
        send_message(partner, "✅ CONNECTED! Start chatting! 🎉")
    else:
        if chat_id not in waiting_users:
            waiting_users.append(chat_id)
        send_message(chat_id, "🔍 Searching for partner...")

def handle_stop(chat_id):
    if chat_id in active_chats:
        partner = active_chats[chat_id]
        send_message(partner, "❌ Partner left chat")
        del active_chats[partner]
        del active_chats[chat_id]
        send_message(chat_id, "✅ Chat ended")
    elif chat_id in waiting_users:
        waiting_users.remove(chat_id)
        send_message(chat_id, "✅ Removed from waiting list")
    else:
        send_message(chat_id, "ℹ️ Not in chat or waiting")

def handle_stats(chat_id):
    stats_text = f"""
📊 Your Stats:
- In chat: {'Yes' if chat_id in active_chats else 'No'}
- Waiting: {'Yes' if chat_id in waiting_users else 'No'}
- Position: {waiting_users.index(chat_id) + 1 if chat_id in waiting_users else 'N/A'}
    """
    send_message(chat_id, stats_text)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
