import sqlite3
import time
from io import BytesIO
import qrcode
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# ===== CONFIG =====
BOT_TOKEN = "7981301072:AAEqY5_6XKmZ_sNMFgorb1hOx1ZDNS0u-Dg"
ADMIN_ID = 7448055431

UPI_ID = "ishan.21@superyes"
MERCHANT_NAME = "Next Hire Bakery"
MIN_BALANCE = 300

bot = telebot.TeleBot(BOT_TOKEN)

# ===== DATABASE =====
conn = sqlite3.connect("bot_data.db", check_same_thread=False)
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS wallets (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount INTEGER,
    status TEXT,
    created_at INTEGER
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS agreements (
    user_id INTEGER PRIMARY KEY,
    agreed INTEGER DEFAULT 0
)
""")
conn.commit()

# ===== HELPERS =====
def get_balance(uid):
    cur.execute("SELECT balance FROM wallets WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return r[0] if r else 0

def add_balance(uid, amt):
    cur.execute(
        "INSERT INTO wallets(user_id, balance) VALUES (?, ?) "
        "ON CONFLICT(user_id) DO UPDATE SET balance = balance + ?",
        (uid, amt, amt)
    )
    conn.commit()

def deduct(uid, amt):
    bal = get_balance(uid)
    if bal >= amt:
        cur.execute("UPDATE wallets SET balance=? WHERE user_id=?", (bal - amt, uid))
        conn.commit()
        return True
    return False

def has_agreed(uid):
    cur.execute("SELECT agreed FROM agreements WHERE user_id=?", (uid,))
    r = cur.fetchone()
    return bool(r and r[0] == 1)

def set_agreed(uid):
    cur.execute("INSERT OR REPLACE INTO agreements(user_id, agreed) VALUES (?,1)", (uid,))
    conn.commit()

def create_payment(uid, amt):
    now = int(time.time())
    cur.execute(
        "INSERT INTO payments(user_id, amount, status, created_at) VALUES (?,?,?,?)",
        (uid, amt, "pending", now)
    )
    conn.commit()
    return cur.lastrowid

# ===== STEPS =====
STEPS = [
    "Step 1 - Buy a old and registerd mobile number from 4sim.in website.",
    "Step 2 - Register Check Karo yaha per👉🏻https://swiggy.com/auth 👉🏻 registerd hoga to direct otp mang lega | nahi hoga to naam ki bolega .",
    "Step 3 - Number buy kar liya ab account ko jo address set hai user ke account mai wahi open karo account .",
    "Step 4 - instamart mai jao 300 ka cart dalkar dekho kitna off aa raha normally better offer hai to theek warna home per jakar box khol lo. ",
    "Step 5 - Important Note 👉🏻 Account Per Free Cash Mil Gaya To Claim Karna Mat Bhul Na Cart Per Warna Aapki Location Per Nahi Lagega Offer"
    "Step 6 - Claim Kar Liya User Ki Location Per Ab Coustmer Ka Ab Aapka Address dalo aur same cart open karo then aapko Free Cash Dikh Jayega."
    "Step 7 - Jaha Tak Order Nahi Ho Jaye Waha Tak Coustmer Ka Address Delete Mat Karna."
]

# ===== START =====
@bot.message_handler(commands=["start"])
def start(msg):
    uid = msg.from_user.id

    if not has_agreed(uid):
        kb = InlineKeyboardMarkup()
        kb.add(
            InlineKeyboardButton("✅ I Agree", callback_data="agree_terms"),
            InlineKeyboardButton("❌ Decline", callback_data="decline_terms")
        )
        bot.send_message(msg.chat.id, "📜 Terms & Conditions\nAgree mandatory.", reply_markup=kb)
        return

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("💸 Swiggy Instamart Trick", callback_data="swiggy_trick"),
        InlineKeyboardButton("💰 Balance", callback_data="check_balance")
    )
    kb.add(
        InlineKeyboardButton("💎 Recharge", callback_data="recharge"),
        InlineKeyboardButton("📩 Support", url="https://t.me/AllYouWantHelp")
    )

    bot.send_message(msg.chat.id, "Welcome 👇", reply_markup=kb)

# ===== ADMIN CALLBACK (FIXED) =====
@bot.callback_query_handler(func=lambda c: c.data.startswith(("confirm_", "reject_")))
def admin_cb(call):
    if call.from_user.id != ADMIN_ID:
        bot.answer_callback_query(call.id, "Unauthorized")
        return

    action, pid = call.data.split("_")
    pid = int(pid)

    cur.execute("SELECT user_id, amount, status FROM payments WHERE id=?", (pid,))
    r = cur.fetchone()

    if not r or r[2] != "pending":
        bot.answer_callback_query(call.id, "Already processed")
        return

    uid, amt, _ = r

    if action == "confirm":
        add_balance(uid, amt)
        cur.execute("UPDATE payments SET status='confirmed' WHERE id=?", (pid,))
        bot.edit_message_text("✅ Approved", call.message.chat.id, call.message.message_id)
        bot.send_message(uid, f"₹{amt} added to wallet.")
    else:
        cur.execute("UPDATE payments SET status='rejected' WHERE id=?", (pid,))
        bot.edit_message_text("❌ Rejected", call.message.chat.id, call.message.message_id)

    conn.commit()
    bot.answer_callback_query(call.id)

# ===== USER CALLBACKS =====
@bot.callback_query_handler(func=lambda c: not c.data.startswith(("confirm_", "reject_")))
def callbacks(call):
    uid = call.from_user.id
    data = call.data

    if data == "agree_terms":
        set_agreed(uid)
        bot.send_message(call.message.chat.id, "✅ Agreed. Use /start")
        return

    if data == "decline_terms":
        bot.send_message(call.message.chat.id, "❌ You must agree.")
        return

    if data == "check_balance":
        bot.send_message(call.message.chat.id, f"💰 Balance: ₹{get_balance(uid)}")
        return

    if data == "swiggy_trick":
        if deduct(uid, MIN_BALANCE):
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Next ➡️", callback_data="step_0"))
            bot.send_message(call.message.chat.id, STEPS[0], reply_markup=kb)
        else:
            bot.send_message(call.message.chat.id, f"Low balance. Pay ₹{MIN_BALANCE}\nUPI: {UPI_ID}")
        return

    if data.startswith("step_"):
        i = int(data.split("_")[1])
        if i < len(STEPS) - 1:
            kb = InlineKeyboardMarkup()
            kb.add(InlineKeyboardButton("Next ➡️", callback_data=f"step_{i+1}"))
            bot.send_message(call.message.chat.id, STEPS[i+1], reply_markup=kb)
        else:
            bot.send_message(call.message.chat.id, "🎉 Completed")
        return

    if data == "recharge":
        kb = InlineKeyboardMarkup()
        for a in [50, 100, 200, 250, 300]:
            kb.add(InlineKeyboardButton(f"💎 {a}", callback_data=f"pay_{a}"))
        bot.send_message(call.message.chat.id, "Select amount", reply_markup=kb)
        return

    if data.startswith("pay_"):
        amt = int(data.split("_")[1])
        upi = f"upi://pay?pa={UPI_ID}&pn={MERCHANT_NAME}&cu=INR&am={amt}"
        img = qrcode.make(upi)
        bio = BytesIO()
        img.save(bio, "PNG")
        bio.seek(0)
        bot.send_photo(call.message.chat.id, bio, caption=f"Pay ₹{amt}\nSend /paid {amt}")

# ===== PAID =====
@bot.message_handler(commands=["paid"])
def paid(msg):
    parts = msg.text.split()
    if len(parts) != 2 or not parts[1].isdigit():
        bot.reply_to(msg, "Usage: /paid <amount>")
        return

    amt = int(parts[1])
    pid = create_payment(msg.from_user.id, amt)

    kb = InlineKeyboardMarkup()
    kb.add(
        InlineKeyboardButton("✅ Approve", callback_data=f"confirm_{pid}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{pid}")
    )

    bot.send_message(
        ADMIN_ID,
        f"Payment Request\nUser: {msg.from_user.id}\nAmount: ₹{amt}\nPID: {pid}",
        reply_markup=kb
    )
    bot.reply_to(msg, "✅ Request sent to admin.")

# ===== RUN =====
print("🤖 Bot starting...")
bot.infinity_polling()