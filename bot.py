import re
import json
import time
import random
import string
import hashlib
import requests
import urllib3
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# Disable warnings for requests verify=False (Stripe calls)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ====== Config =======
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'
AUTHORIZED_USERS = [5248903529, 7081556047, 5519289321]
SUPPORT_GROUP = -1002568201025
SUPPORT_USERNAME = '@UNDIFINED_CC'
OWNER = '@SIDIKI_MUSTAFA_92'
USERS_FILE = 'users.txt'

# ====== Helper functions ======

def save_user(user_id: int):
    try:
        with open(USERS_FILE, 'r') as f:
            users = f.read().splitlines()
    except FileNotFoundError:
        users = []
    if str(user_id) not in users:
        with open(USERS_FILE, 'a') as f:
            f.write(f"{user_id}\n")

def is_registered(user_id: int) -> bool:
    try:
        with open(USERS_FILE, 'r') as f:
            users = f.read().splitlines()
        return str(user_id) in users
    except FileNotFoundError:
        return False

def is_authorized(user_id: int) -> bool:
    return user_id in AUTHORIZED_USERS

def extract_cc(text: str):
    # Example formats:
    # 1234567812345678|12|25|123
    # 1234567812345678 12 25 123
    pattern = r'(\d{16})\D+(\d{2})\D+(\d{2,4})\D+(\d{3})'
    match = re.search(pattern, text)
    if match:
        cc = match.group(1)
        month = match.group(2)
        year = match.group(3)
        if len(year) == 4:
            year = year[2:]  # last two digits of year
        cvv = match.group(4)
        return cc, month, year, cvv
    return None

def generate_random_user():
    first = ''.join(random.choices(string.ascii_lowercase, k=7)).capitalize()
    last = ''.join(random.choices(string.ascii_lowercase, k=7)).capitalize()
    domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
    email = f"{first}{random.randint(100,999)}@{random.choice(domains)}"
    return first, last, email

def check_cc_api(cc, month, year, cvv):
    # This simulates the Stripe token + charge flow (simplified)
    first, last, email = generate_random_user()
    headers_token = {
        'accept': 'application/json',
        'content-type': 'application/x-www-form-urlencoded',
        'user-agent': 'Mozilla/5.0'
    }
    data_token = {
        'card[number]': cc,
        'card[exp_month]': month,
        'card[exp_year]': year,
        'card[cvc]': cvv,
        'card[name]': f"{first} {last}",
        'key': 'pk_test_51RPHEyPKJT4UzOPvV7tWHMGotxjGV6iFmwOBXud6HBmL9NezxGlc0Gk6meBt6U6nrP1diGkPfnCDTIEJLKiFE0yQ00uiHrER4E'
    }
    try:
        res_token = requests.post('https://api.stripe.com/v1/tokens', headers=headers_token, data=data_token, verify=False, timeout=15)
        token_json = res_token.json()
        if 'id' not in token_json:
            error_msg = token_json.get('error', {}).get('message', 'Failed to generate token')
            return False, error_msg

        # Fake charge simulation (replace with real charge if you want)
        # For demo, just consider token success = card success
        return True, 'Charge simulation successful'
    except Exception as e:
        return False, str(e)

def get_bin_info(bin_num):
    try:
        res = requests.get(f"https://lookup.binlist.net/{bin_num}", timeout=10)
        if res.status_code == 200:
            return res.json()
    except:
        return None
    return None

def generate_card(bin_prefix):
    card = bin_prefix
    while len(card) < 15:
        card += str(random.randint(0, 9))
    # Luhn check digit
    def luhn_checksum(card_number):
        def digits_of(n):
            return [int(d) for d in str(n)]
        digits = digits_of(card_number)
        odd_sum = sum(digits[-1::-2])
        even_sum = 0
        for d in digits[-2::-2]:
            d = d*2
            if d > 9:
                d -= 9
            even_sum += d
        return (odd_sum + even_sum) % 10
    check_digit = (10 - luhn_checksum(card)) % 10
    return card + str(check_digit)

# ====== Bot command handlers ======

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = f"""Welcome to CC Bot!

Commands:
/register - Register yourself
/chk <cc|mm|yy|cvv> - Check a credit card
/bin <6 digit BIN> - Get BIN info
/gen <6 digit BIN> - Generate card

Bot by: {OWNER}
"""
    await update.message.reply_text(text)

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    save_user(user_id)
    await update.message.reply_text("✅ Registered! Use the bot in " + SUPPORT_USERNAME)

async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_registered(user_id):
        await update.message.reply_text("❌ You must /register first!")
        return
    if update.message.chat.type == 'private' and not is_authorized(user_id):
        await update.message.reply_text(f"❌ Use this bot only in the group: {SUPPORT_USERNAME}")
        return

    text = update.message.text
    cc_data = extract_cc(text)
    if not cc_data:
        await update.message.reply_text("❌ Invalid CC format!\nUse: 1234567812345678|12|25|123")
        return

    cc, mm, yy, cvv = cc_data

    # Run blocking check in thread to not block event loop
    success, msg = await asyncio.to_thread(check_cc_api, cc, mm, yy, cvv)
    emoji = "✅" if success else "❌"
    current_time = time.strftime('%I:%M:%S %p')

    resp = f"""
𝗖𝗖: {cc}
𝗘𝘅𝗽: {mm}/{yy}
𝗖𝗩𝗩: {cvv}

Status: {emoji} {msg}
Time: {current_time}
"""
    await update.message.reply_text(resp)

async def bin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args[0]) < 6:
        await update.message.reply_text("❌ Please provide a valid 6-digit BIN\nUsage: /bin 414720")
        return
    bin_num = context.args[0][:6]
    info = await asyncio.to_thread(get_bin_info, bin_num)
    if not info:
        await update.message.reply_text("❌ BIN info not found or error")
        return

    brand = info.get('brand', 'N/A')
    scheme = info.get('scheme', 'N/A')
    card_type = info.get('type', 'N/A')
    country = info.get('country', {}).get('name', 'N/A')
    bank = info.get('bank', {}).get('name', 'N/A')

    resp = f"""BIN: {bin_num}
Scheme: {scheme}
Brand: {brand}
Type: {card_type}
Country: {country}
Bank: {bank}
"""
    await update.message.reply_text(resp)

async def gen_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args[0]) < 6:
        await update.message.reply_text("❌ Please provide a valid 6-digit BIN\nUsage: /gen 414720")
        return
    bin_prefix = context.args[0][:6]
    card_number = generate_card(bin_prefix)
    await update.message.reply_text(f"Generated Card:\n{card_number}|12|25|123")

# ====== Main ======
async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("register", register))
    app.add_handler(CommandHandler("chk", chk))
    app.add_handler(CommandHandler("bin", bin_command))
    app.add_handler(CommandHandler("gen", gen_command))

    # Also respond to messages starting with .chk
    async def dot_chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # just call chk handler with message text
        await chk(update, context)

    app.add_handler(MessageHandler(filters.TEXT & filters.Regex(r'^\.(chk)'), dot_chk))

    print("Bot is starting...")
    await app.run_polling()

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
