from flask import Flask, request
import requests
import os
import json
import sqlite3
from datetime import datetime, timedelta
import hashlib

app = Flask(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN', "8080306073:AAHy6IO4j_uResEEN_H2K-PJ2TkPws79mH8")
TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Payment bot configuration
PAYMENT_BOT_URL = "https://chattelo-support-bot.onrender.com"

waiting_users = []
active_chats = {}

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS premium_users
                 (user_id INTEGER PRIMARY KEY, 
                  premium_until TEXT,
                  payment_date TEXT,
                  premium_code TEXT UNIQUE,
                  stars_received INTEGER DEFAULT 0)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS used_codes
                 (code TEXT PRIMARY KEY,
                  user_id INTEGER,
                  used_at TEXT)''')
    conn.commit()
    conn.close()

def is_premium(user_id):
    """Check if user has active premium subscription"""
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    c.execute("SELECT premium_until FROM premium_users WHERE user_id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        premium_until = datetime.fromisoformat(result[0])
        return datetime.now() < premium_until
    return False

def activate_premium_with_code(user_id, premium_code, duration_days=30):
    """Activate premium using code from payment bot"""
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    
    # Check if code was already used
    c.execute("SELECT * FROM used_codes WHERE code = ?", (premium_code,))
    if c.fetchone():
        conn.close()
        return False, "❌ This code has already been used!"
    
    # Verify code format (basic validation)
    if not premium_code.startswith('CHATTELO-'):
        conn.close()
        return False, "❌ Invalid premium code format!"
    
    # 🚨 CRITICAL FIX: Verify with payment bot API before activation
    is_valid, verified_user_id, verification_message = verify_premium_code_with_bot(premium_code)
    
    if not is_valid:
        conn.close()
        return False, f"❌ Invalid premium code: {verification_message}"
    
    # Additional security: Ensure code belongs to this user
    if verified_user_id and verified_user_id != user_id:
        conn.close()
        return False, "❌ This premium code was issued to another user!"
    
    # Activate premium
    premium_until = datetime.now() + timedelta(days=duration_days)
    
    c.execute('''INSERT OR REPLACE INTO premium_users 
                 (user_id, premium_until, payment_date, premium_code) 
                 VALUES (?, ?, ?, ?)''', 
              (user_id, premium_until.isoformat(), datetime.now().isoformat(), premium_code))
    
    # Mark code as used
    c.execute('''INSERT INTO used_codes (code, user_id, used_at)
                 VALUES (?, ?, ?)''', 
              (premium_code, user_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    return True, "✅ Premium activated successfully!"

def verify_premium_code_with_bot(premium_code):
    """Verify premium code with payment bot API"""
    try:
        # Call payment bot API to verify code
        response = requests.get(
            f"{PAYMENT_BOT_URL}/verify_code/{premium_code}",
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('valid', False), data.get('user_id'), data.get('message', '')
        return False, None, "❌ Verification service unavailable"
    except Exception as e:
        print(f"❌ Verification API error: {e}")
        return False, None, "❌ Could not verify code"

def add_premium_user(user_id, duration_days=30):
    """Add user to premium for specified days (backup method)"""
    premium_until = datetime.now() + timedelta(days=duration_days)
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO premium_users 
                 (user_id, premium_until, payment_date) 
                 VALUES (?, ?, ?)''', 
              (user_id, premium_until.isoformat(), datetime.now().isoformat()))
    conn.commit()
    conn.close()

def record_stars_payment(user_id, stars_amount):
    """Record stars payment and take 20% commission"""
    net_stars = int(stars_amount * 0.8)  # We keep 20%
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    c.execute('''UPDATE premium_users SET stars_received = stars_received + ? 
                 WHERE user_id = ?''', (net_stars, user_id))
    conn.commit()
    conn.close()
    return net_stars

def send_message(chat_id, text):
    try:
        response = requests.post(
            f"{TELEGRAM_URL}/sendMessage", 
            json={'chat_id': chat_id, 'text': text}
        )
        return True
    except:
        return False

def send_message_with_buttons(chat_id, text, is_premium_user=False):
    """Send message with appropriate buttons based on premium status"""
    if is_premium_user:
        buttons = [
            [{"text": "🔍 Find Partner", "callback_data": "find"}],
            [{"text": "🛑 Stop Chat", "callback_data": "stop"}],
            [{"text": "💰 Send Stars", "callback_data": "send_stars"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "💎 Premium Info", "callback_data": "premium_info"}]
        ]
    else:
        buttons = [
            [{"text": "🔍 Find Partner", "callback_data": "find"}],
            [{"text": "🛑 Stop Chat", "callback_data": "stop"}],
            [{"text": "💎 Get Premium", "callback_data": "get_premium"}],
            [{"text": "📊 My Stats", "callback_data": "stats"}],
            [{"text": "🔑 Enter Code", "callback_data": "enter_code"}]
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

def send_premium_instructions(chat_id):
    """Send instructions for getting premium"""
    instructions = """
💎 *GET PREMIUM ACCESS*

To unlock premium features:
1. Go to @ChatteloSupportBot
2. Send /buy_premium command
3. Pay $10.99 via cryptocurrency
4. Get your premium code instantly!
5. Return here and enter your code

✨ *Premium Features:*
• Send Photos 📸
• Send Voice Messages 🎤
• Receive Telegram Stars 💫
• Priority Matching ⚡

💰 *Only $10.99 for 30 days!*

Click 'Enter Code' after payment!
    """
    send_message(chat_id, instructions)

@app.route('/')
def home():
    return "🤖 Premium Bot with CODE VERIFICATION is RUNNING!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    
    # Handle button clicks
    if 'callback_query' in data:
        callback = data['callback_query']
        chat_id = callback['message']['chat']['id']
        button_data = callback['data']
        user_is_premium = is_premium(chat_id)
        
        if button_data == 'find':
            handle_chat(chat_id)
        elif button_data == 'stop':
            handle_stop(chat_id)
        elif button_data == 'stats':
            handle_stats(chat_id, user_is_premium)
        elif button_data == 'get_premium':
            send_premium_instructions(chat_id)
        elif button_data == 'premium_info':
            handle_premium_info(chat_id)
        elif button_data == 'send_stars' and user_is_premium:
            handle_send_stars(chat_id)
        elif button_data == 'enter_code':
            handle_enter_code(chat_id)
        
        # Tell Telegram we received the button click
        requests.post(f"{TELEGRAM_URL}/answerCallbackQuery", 
                     json={'callback_query_id': callback['id']})
        return "OK"
    
    # Handle normal messages
    if 'message' in data:
        chat_id = data['message']['chat']['id']
        user_is_premium = is_premium(chat_id)
        
        # Handle photos (premium feature)
        if 'photo' in data['message']:
            if user_is_premium:
                if chat_id in active_chats:
                    # Forward photo to partner
                    photo = data['message']['photo'][-1]  # Get highest quality
                    send_photo(active_chats[chat_id], photo['file_id'], "📸 Photo from partner")
                else:
                    send_message(chat_id, "❌ You're not in a chat. Find a partner first!")
            else:
                send_message(chat_id, "❌ Premium feature! Get premium to send photos. Click 'Get Premium' button")
            return "OK"
        
        # Handle voice messages (premium feature)
        if 'voice' in data['message']:
            if user_is_premium:
                if chat_id in active_chats:
                    # Forward voice to partner
                    voice = data['message']['voice']
                    send_voice(active_chats[chat_id], voice['file_id'], "🎤 Voice message from partner")
                else:
                    send_message(chat_id, "❌ You're not in a chat. Find a partner first!")
            else:
                send_message(chat_id, "❌ Premium feature! Get premium to send voice messages. Click 'Get Premium' button")
            return "OK"
        
        # Handle text messages
        text = data['message'].get('text', '').strip()
        
        if text == '/start':
            welcome_text = "👋 Welcome to Chattelo!\n\n"
            if user_is_premium:
                welcome_text += "💎 *PREMIUM USER* - You can send photos & voice messages!\n\n"
            else:
                welcome_text += "✨ Get premium to unlock photos & voice messages!\n\n"
            welcome_text += "Click buttons below:"
            send_message_with_buttons(chat_id, welcome_text, user_is_premium)
            
        elif text == '/chat':
            handle_chat(chat_id)
        elif text == '/stop':
            handle_stop(chat_id)
        elif text == '/premium':
            send_premium_instructions(chat_id)
        elif text.startswith('/activate'):
            # Handle premium code activation
            parts = text.split()
            if len(parts) == 2:
                premium_code = parts[1]
                handle_premium_activation(chat_id, premium_code)
            else:
                send_message(chat_id, "❌ Usage: /activate YOUR_PREMIUM_CODE")
        elif text.startswith('CHATTELO-'):
            # Auto-detect premium code format
            handle_premium_activation(chat_id, text)
        else:
            if chat_id in active_chats:
                partner_id = active_chats[chat_id]
                partner_is_premium = is_premium(partner_id)
                
                # Add premium badge if sender is premium
                message_prefix = "💎 " if user_is_premium else ""
                send_message(partner_id, f"{message_prefix}💬 {text}")
            else:
                send_message(chat_id, "❌ Use /chat first or click 'Find Partner' button")
    
    return "OK"

def handle_enter_code(chat_id):
    """Prompt user to enter premium code"""
    instructions = """
🔑 *Enter Premium Code*

Please enter your premium code that you received from @ChatteloSupportBot:

You can either:
1. Type: `/activate YOUR_CODE_HERE`
2. Or just paste the code: `CHATTELO-XXXXX-XXX`

Example: `/activate CHATTELO-ABC12-345`
    """
    send_message(chat_id, instructions)

def handle_premium_activation(chat_id, premium_code):
    """Activate premium using code from payment bot"""
    # Clean the code
    premium_code = premium_code.strip().upper()
    
    # Send verification message
    send_message(chat_id, "🔍 Verifying your premium code with payment system...")
    
    # Verify and activate premium
    success, message = activate_premium_with_code(chat_id, premium_code)
    
    if success:
        send_message(chat_id, f"🎉 {message}\n\n💎 You now have PREMIUM ACCESS for 30 days!")
        send_message_with_buttons(chat_id, "💎 PREMIUM ACTIVATED! Unlocked photos & voice messages!", True)
        
        # Log the activation
        print(f"✅ Premium activated for user {chat_id} with code: {premium_code}")
    else:
        send_message(chat_id, f"❌ {message}\n\nPlease check your code and try again.")
        
        # Offer help
        send_message(chat_id, "💡 Need help? Contact @behar5057 or make sure you:\n1. Paid successfully\n2. Received code from @ChatteloSupportBot\n3. Entered code correctly")

def handle_chat(chat_id):
    if chat_id in active_chats:
        send_message(chat_id, "❌ Already in chat! Click 'Stop Chat' first")
        return
        
    if waiting_users and waiting_users[0] != chat_id:
        partner = waiting_users.pop(0)
        active_chats[chat_id] = partner
        active_chats[partner] = chat_id
        
        # Notify both users about premium status
        user_premium = is_premium(chat_id)
        partner_premium = is_premium(partner)
        
        user_msg = "✅ CONNECTED! Start chatting! 🎉"
        if partner_premium:
            user_msg += "\n💎 Your partner has PREMIUM - they can send photos & voice!"
        
        partner_msg = "✅ CONNECTED! Start chatting! 🎉"
        if user_premium:
            partner_msg += "\n💎 Your partner has PREMIUM - they can send photos & voice!"
        
        send_message(chat_id, user_msg)
        send_message(partner, partner_msg)
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

def handle_stats(chat_id, is_premium_user):
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    
    if is_premium_user:
        c.execute("SELECT premium_until, stars_received, premium_code FROM premium_users WHERE user_id = ?", (chat_id,))
        result = c.fetchone()
        premium_until = datetime.fromisoformat(result[0])
        stars_received = result[1] or 0
        premium_code = result[2]
        
        stats_text = f"""
📊 *Your Premium Stats:*
- Premium Status: ✅ ACTIVE
- Premium Code: {premium_code}
- Premium Until: {premium_until.strftime('%Y-%m-%d')}
- Stars Received: {stars_received} ⭐
- In chat: {'Yes' if chat_id in active_chats else 'No'}
- Waiting: {'Yes' if chat_id in waiting_users else 'No'}
        """
    else:
        stats_text = f"""
📊 *Your Stats:*
- Premium Status: ❌ INACTIVE
- In chat: {'Yes' if chat_id in active_chats else 'No'}
- Waiting: {'Yes' if chat_id in waiting_users else 'No'}
- Position: {waiting_users.index(chat_id) + 1 if chat_id in waiting_users else 'N/A'}

✨ Get premium for more features!
        """
    
    conn.close()
    send_message(chat_id, stats_text)

def handle_premium_info(chat_id):
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    c.execute("SELECT premium_until, stars_received, premium_code FROM premium_users WHERE user_id = ?", (chat_id,))
    result = c.fetchone()
    conn.close()
    
    if result:
        premium_until = datetime.fromisoformat(result[0])
        stars_received = result[1] or 0
        premium_code = result[2]
        
        info_text = f"""
💎 *Your Premium Information:*
- Premium Code: {premium_code}
- Premium Until: {premium_until.strftime('%Y-%m-%d %H:%M')}
- Stars Earned: {stars_received} ⭐
- Days Left: {(premium_until - datetime.now()).days}

✨ *Premium Features Active:*
• Send Photos 📸
• Send Voice Messages 🎤
• Receive Telegram Stars 💫
• Priority Matching ⚡
        """
    else:
        info_text = "❌ You don't have an active premium subscription."
    
    send_message(chat_id, info_text)

def handle_send_stars(chat_id):
    """Instructions for sending Telegram Stars"""
    stars_info = """
💫 *Send Telegram Stars*

To send stars to your chat partner:
1. Make sure you're in an active chat
2. Your partner must have premium
3. Use Telegram's native stars feature
4. We take 20% commission for platform maintenance

💰 *Example:* Send 100 stars → Partner gets 80 stars

Note: Both users need premium for star transactions.
    """
    send_message(chat_id, stars_info)

def send_photo(chat_id, file_id, caption=""):
    """Send photo to user"""
    payload = {
        'chat_id': chat_id,
        'photo': file_id,
        'caption': caption
    }
    try:
        requests.post(f"{TELEGRAM_URL}/sendPhoto", json=payload)
        return True
    except:
        return False

def send_voice(chat_id, file_id, caption=""):
    """Send voice message to user"""
    payload = {
        'chat_id': chat_id,
        'voice': file_id,
        'caption': caption
    }
    try:
        requests.post(f"{TELEGRAM_URL}/sendVoice", json=payload)
        return True
    except:
        return False

# API endpoint for payment bot to verify codes
@app.route('/api/verify_code/<premium_code>', methods=['GET'])
def verify_code_api(premium_code):
    """API endpoint for payment bot to verify codes"""
    conn = sqlite3.connect('premium_users.db')
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM used_codes WHERE code = ?", (premium_code,))
    result = c.fetchone()
    conn.close()
    
    if result:
        return {
            'valid': True,
            'user_id': result[0],
            'message': 'Code is valid and activated'
        }
    else:
        return {
            'valid': False,
            'user_id': None,
            'message': 'Code not found or not activated'
        }

# Initialize database on startup
init_db()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)
