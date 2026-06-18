# ============================================
# ربات تلگرام با انیمیشن ویرایش‌شونده و اتصال به کاگل
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
user_data = {}
cooldown_seconds = 30

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
    reset_if_needed(user_id)
    data = get_user_data(user_id)
    
    if data["count"] >= 20:
        return False, 0
    
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

# ========== اتصال به کاگل (واقعی) ==========
def ask_kaggle(prompt: str) -> str:
    """
    ارسال سوال به کاگل و دریافت پاسخ واقعی
    """
    try:
        # اینجا باید کد واقعی برای اجرای نوت‌بوک کاگل رو بزنی
        # مثلاً با استفاده از kagglehub یا requests به API کاگل
        
        # فعلاً یه پاسخ نمونه برای تست
        return "این پاسخ از کاگل هست! به زودی وصل میشه."
        
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

# ========== پیام‌های معمولی با انیمیشن ویرایش‌شونده ==========
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
    
    # ========== انیمیشن با نوار پیشرفت (ویرایش‌شونده) ==========
    progress_messages = [
        ("🤔 **Analyzing your question...**", 0.2),
        ("🧠 **Processing with Mistral-7B...**", 0.4),
        ("⚡ **Fetching the best response...**", 0.7),
        ("✨ **Almost there!**", 0.9)
    ]
    
    # ارسال پیام اول
    bar_length = 20
    filled = int(bar_length * 0.1)
    bar = "█" * filled + "░" * (bar_length - filled)
    first_msg = await update.message.reply_text(
        f"🤔 **Thinking...**\n`[{bar}] 10%`",
        parse_mode="Markdown"
    )
    
    # ویرایش پیام برای هر مرحله
    for i, (msg, progress) in enumerate(progress_messages):
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        progress_text = f"{msg}\n`[{bar}] {int(progress*100)}%`"
        
        await first_msg.edit_text(progress_text, parse_mode="Markdown")
        await asyncio.sleep(1.0 if i < len(progress_messages)-1 else 0.5)
    
    # ========== گرفتن پاسخ واقعی از کاگل ==========
    response = ask_kaggle(prompt)
    
    # به‌روزرسانی سهمیه و تاریخچه
    increment_count(user_id)
    add_history(user_id, prompt, response)
    remaining = get_remaining(user_id)
    
    # ========== ویرایش پیام انیمیشن به پاسخ نهایی ==========
    await first_msg.edit_text(
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
