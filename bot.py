# ============================================
# ربات تلگرام متصل به کاگل - نسخه نهایی
# ============================================
import os
import sys
import logging
import asyncio
import subprocess
import tempfile
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== تنظیم لاگ ==========
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ========== نصب خودکار kagglehub ==========
try:
    import kagglehub
    logger.info("✅ kagglehub نصب است.")
except ImportError:
    logger.info("⏳ در حال نصب kagglehub...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "kagglehub"])
    logger.info("✅ kagglehub نصب شد!")

# ========== تنظیمات از Environment Variables ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME")
KAGGLE_KERNEL_SLUG = os.environ.get("KAGGLE_KERNEL_SLUG")
KAGGLE_API_TOKEN = os.environ.get("KAGGLE_API_TOKEN")

if not TELEGRAM_TOKEN:
    logger.error("❌ TELEGRAM_TOKEN not set!")
    sys.exit(1)

logger.info("🚀 ربات در حال راه‌اندازی...")
logger.info(f"📊 KAGGLE_USERNAME: {KAGGLE_USERNAME}")
logger.info(f"📊 KAGGLE_KERNEL_SLUG: {KAGGLE_KERNEL_SLUG}")

# ========== تنظیمات ==========
COOLDOWN_SECONDS = 30
MAX_DAILY_MESSAGES = 20
user_data = {}

# ========== توابع دیتابیس ==========
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
    
    if data["count"] >= MAX_DAILY_MESSAGES:
        return False, 0
    
    if data["last_message"] is not None:
        elapsed = (datetime.now() - data["last_message"]).total_seconds()
        if elapsed < COOLDOWN_SECONDS:
            return False, int(COOLDOWN_SECONDS - elapsed)
    
    return True, 0

def increment_count(user_id: str):
    data = get_user_data(user_id)
    data["count"] += 1
    data["last_message"] = datetime.now()
    logger.info(f"📊 کاربر {user_id}: پیام شماره {data['count']}")

def get_remaining(user_id: str) -> int:
    reset_if_needed(user_id)
    return MAX_DAILY_MESSAGES - get_user_data(user_id)["count"]

def add_history(user_id: str, user_msg: str, bot_response: str):
    data = get_user_data(user_id)
    data["history"].append({"user": user_msg, "bot": bot_response})
    if len(data["history"]) > 10:
        data["history"] = data["history"][-10:]

# ========== اتصال به کاگل با kagglehub ==========
def ask_kaggle(prompt: str) -> str:
    logger.info(f"⏳ ارسال سوال به کاگل: {prompt[:50]}...")
    
    try:
        import kagglehub
        import os
        
        os.environ["KAGGLE_API_TOKEN"] = KAGGLE_API_TOKEN
        
        logger.info("⏳ در حال اجرای نوت‌بوک روی کاگل...")
        result = kagglehub.kernel_run(
            f"{KAGGLE_USERNAME}/{KAGGLE_KERNEL_SLUG}",
            args=[prompt]
        )
        
        logger.info(f"✅ پاسخ دریافت شد: {result[:50]}...")
        return result.strip()
        
    except Exception as e:
        logger.error(f"❌ خطا: {str(e)}")
        return f"❌ خطا: {str(e)}"

# ========== دستورات ربات ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    logger.info(f"📩 /start از کاربر {user_id}")
    remaining = get_remaining(user_id)
    
    try:
        await update.message.reply_text(
            f"🤖 Welcome to Mistral AI Bot!\n\n"
            f"You have {remaining}/{MAX_DAILY_MESSAGES} messages today.\n"
            f"You can send one message every {COOLDOWN_SECONDS} seconds.\n\n"
            f"Type /help for more info."
        )
        logger.info(f"✅ /start برای کاربر {user_id} ارسال شد")
    except Exception as e:
        logger.error(f"❌ خطا در /start: {str(e)}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    logger.info(f"📩 /help از کاربر {user_id}")
    remaining = get_remaining(user_id)
    
    try:
        await update.message.reply_text(
            f"📖 Help & Commands\n\n"
            f"/start - Start the bot\n"
            f"/help - Show this message\n"
            f"/remaining - Check your remaining messages\n\n"
            f"Daily Limit: {MAX_DAILY_MESSAGES} messages\n"
            f"Cooldown: {COOLDOWN_SECONDS} seconds\n"
            f"Remaining Today: {remaining}/{MAX_DAILY_MESSAGES}"
        )
        logger.info(f"✅ /help برای کاربر {user_id} ارسال شد")
    except Exception as e:
        logger.error(f"❌ خطا در /help: {str(e)}")

async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    logger.info(f"📩 /remaining از کاربر {user_id}")
    remaining = get_remaining(user_id)
    
    try:
        await update.message.reply_text(
            f"Remaining Messages: {remaining}/{MAX_DAILY_MESSAGES}\n"
            f"Resets at midnight UTC."
        )
        logger.info(f"✅ /remaining برای کاربر {user_id} ارسال شد")
    except Exception as e:
        logger.error(f"❌ خطا در /remaining: {str(e)}")

# ========== مدیریت پیام‌ها ==========
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    prompt = update.message.text
    logger.info(f"📩 پیام از کاربر {user_id}: {prompt[:50]}...")
    
    allowed, wait_time = can_ask(user_id)
    if not allowed:
        if wait_time > 0:
            await update.message.reply_text(
                f"Please wait {wait_time} seconds before sending another message."
            )
        else:
            await update.message.reply_text(
                f"Daily limit reached! You have used {MAX_DAILY_MESSAGES}/{MAX_DAILY_MESSAGES} today."
            )
        return
    
    try:
        # پیام اولیه
        msg = await update.message.reply_text("⏳ Thinking...")
        
        # گرفتن پاسخ از کاگل
        response = ask_kaggle(prompt)
        
        # به‌روزرسانی آمار
        increment_count(user_id)
        add_history(user_id, prompt, response)
        remaining = get_remaining(user_id)
        
        # ارسال پاسخ نهایی
        await msg.edit_text(
            f"💬 Response:\n{response}\n\n"
            f"Remaining Today: {remaining}/{MAX_DAILY_MESSAGES}"
        )
        logger.info(f"✅ پاسخ برای کاربر {user_id} ارسال شد")
        
    except Exception as e:
        logger.error(f"❌ خطا در پردازش پیام: {str(e)}")
        try:
            await update.message.reply_text(f"❌ خطا: {str(e)}")
        except:
            logger.error("❌ حتی ارسال پیام خطا هم ناموفق بود!")

# ========== اجرا ==========
def main():
    logger.info("🚀 ربات در حال اجرا...")
    
    try:
        app = Application.builder().token(TELEGRAM_TOKEN).build()
        logger.info("✅ اپلیکیشن ساخته شد")
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("remaining", remaining))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        logger.info("✅ هندلرها اضافه شدند")
        
        logger.info("🚀 شروع به Polling...")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"❌ خطا در اجرای اصلی: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
