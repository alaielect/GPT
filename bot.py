# ============================================
# ربات تلگرام با محدودیت، تایمر و انیمیشن
# ============================================
import os
import time
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests
import subprocess

# ========== تنظیمات ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KAGGLE_TOKEN = os.environ.get("KAGGLE_API_TOKEN")
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME")
KAGGLE_KERNEL_SLUG = os.environ.get("KAGGLE_KERNEL_SLUG")

# ========== دیتابیس ساده ==========
user_data = {}  # {user_id: {"count": 0, "last_reset": "2024-01-01", "last_message": None, "history": []}}
cooldown_seconds = 30  # ۳۰ ثانیه تاخیر بین پیام‌ها

def get_user_data(user_id: str) -> dict:
    if user_id not in user_data:
        user_data[user_id] = {
            "count": 0,
            "last_reset": datetime.now().strftime("%Y-%m-%d"),
            "last_message": None,
            "history": []
        }
    return user_data[user_id]

def reset_if_needed(user_id: str):
    data = get_user_data(user_id)
    today = datetime.now().strftime("%Y-%m-%d")
    if data["last_reset"] != today:
        data["count"] = 0
        data["last_reset"] = today
        data["history"] = []

def can_ask(user_id: str) -> tuple:
    """
    بررسی می‌کند که کاربر می‌تواند سوال بپرسد یا نه.
    برمی‌گرداند: (مجاز است؟, زمان باقی‌مانده به ثانیه)
    """
    reset_if_needed(user_id)
    data = get_user_data(user_id)
    
    # چک کردن محدودیت روزانه
    if data["count"] >= 20:
        return False, 0
    
    # چک کردن تاخیر ۳۰ ثانیه‌ای
    if data["last_message"] is not None:
        elapsed = (datetime.now() - data["last_message"]).total_seconds()
        if elapsed < cooldown_seconds:
            return False, int(cooldown_seconds - elapsed)
    
    return True, 0

def increment_count(user_id: str):
    data = get_user_data(user_id)
    data["count"] += 1
    data["last_message"] = datetime.now()

def get_remaining(user_id: str) -> int:
    reset_if_needed(user_id)
    return 20 - get_user_data(user_id)["count"]

def add_history(user_id: str, user_msg: str, bot_response: str):
    data = get_user_data(user_id)
    data["history"].append({"user": user_msg, "bot": bot_response})
    if len(data["history"]) > 10:
        data["history"] = data["history"][-10:]

# ========== اتصال به کاگل ==========
def ask_kaggle(prompt: str) -> str:
    """
    ارسال سوال به کاگل و دریافت پاسخ
    (این قسمت رو با روش اتصال به کاگل که انتخاب کردی، جایگزین کن)
    """
    # این یک نمونه است. باید با روش واقعی ارتباط با کاگل جایگزین بشه.
    try:
        # مثال: ارسال به یک API
        response = requests.post(
            "https://your-kaggle-api.com/run",
            json={"prompt": prompt, "token": KAGGLE_TOKEN},
            timeout=90
        )
        if response.status_code == 200:
            return response.json().get("response", "❌ پاسخی دریافت نشد!")
        else:
            return f"❌ خطا: {response.status_code}"
    except Exception as e:
        return f"❌ خطا: {str(e)}"

# ========== دستورات ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    remaining = get_remaining(user_id)
    
    await update.message.reply_text(
        f"🤖 **Welcome to Mistral AI Bot!**\n\n"
        f"• I'm powered by **Mistral-7B** on Kaggle GPU.\n"
        f"• You have **{remaining}/20** messages remaining today.\n"
        f"• You can send one message every **{cooldown_seconds} seconds**.\n"
        f"• Ask me anything! 🤔\n\n"
        f"📖 Type /help for more info.",
        parse_mode="Markdown"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    remaining = get_remaining(user_id)
    
    await update.message.reply_text(
        f"📖 **Help & Commands**\n\n"
        f"• /start - Start the bot\n"
        f"• /help - Show this message\n"
        f"• /remaining - Check your remaining messages\n\n"
        f"💰 **Daily Limit:** 20 messages per day\n"
        f"⏰ **Cooldown:** {cooldown_seconds} seconds between messages\n"
        f"📊 **Remaining Today:** {remaining}/20\n\n"
        f"⚡ Powered by Kaggle GPU (Tesla T4 × 2)",
        parse_mode="Markdown"
    )

async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    remaining = get_remaining(user_id)
    await update.message.reply_text(
        f"📊 **Remaining Messages:** {remaining}/20\n"
        f"⏰ Resets at midnight UTC.",
        parse_mode="Markdown"
    )

# ========== پیام‌های معمولی ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prompt = update.message.text
    
    # چک کردن مجوز
    allowed, wait_time = can_ask(user_id)
    if not allowed:
        if wait_time > 0:
            await update.message.reply_text(
                f"⏳ **Please wait {wait_time} seconds** before sending another message.",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"❌ **Daily limit reached!**\n"
                f"You have used 20/20 messages today.\n"
                f"⏰ Please try again tomorrow.",
                parse_mode="Markdown"
            )
        return
    
    # ========== انیمیشن با نوار پیشرفت ==========
    progress_messages = [
        ("🤔 **Analyzing your question...**", 0.2),
        ("🧠 **Processing with Mistral-7B...**", 0.4),
        ("⚡ **Fetching the best response...**", 0.7),
        ("✨ **Almost there!**", 0.9)
    ]
    
    # ارسال پیام‌های انیمیشنی با نوار پیشرفت
    last_msg = None
    for i, (msg, progress) in enumerate(progress_messages):
        # ساخت نوار پیشرفت
        bar_length = 20
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        progress_text = f"{msg}\n`[{bar}] {int(progress*100)}%`"
        
        if last_msg is None:
            last_msg = await update.message.reply_text(progress_text, parse_mode="Markdown")
        else:
            await last_msg.edit_text(progress_text, parse_mode="Markdown")
        
        # فاصله زمانی متناسب با مرحله
        await asyncio.sleep(1.0 if i < len(progress_messages)-1 else 0.5)
    
    # ========== گرفتن پاسخ ==========
    # اینجا باید پاسخ واقعی رو از کاگل بگیری
    # response = ask_kaggle(prompt)  # این خط رو وقتی وصل شدی، فعال کن
    
    # برای تست فعلی، یه پاسخ ساختگی
    response = "این یه پاسخ تستی از رباته! بعد از اتصال به کاگل، جواب واقعی رو میگیری."
    
    # به‌روزرسانی سهمیه و تاریخچه
    increment_count(user_id)
    add_history(user_id, prompt, response)
    remaining = get_remaining(user_id)
    
    # ارسال پاسخ نهایی
    await update.message.reply_text(
        f"💬 **Response:**\n{response}\n\n"
        f"📊 **Remaining Today:** {remaining}/20\n"
        f"⏳ Next message available in {cooldown_seconds} seconds.",
        parse_mode="Markdown"
    )

# ========== اجرا ==========
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("remaining", remaining))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🚀 Bot is running!")
    app.run_polling()

if __name__ == "__main__":
    main()
