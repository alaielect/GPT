# ============================================
# ربات تلگرام متصل به کاگل با روش تضمینی
# ============================================
import os
import sys
import time
import asyncio
import subprocess
import tempfile
from datetime import datetime
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ========== تنظیمات از Environment Variables ==========
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
KAGGLE_USERNAME = os.environ.get("KAGGLE_USERNAME")
KAGGLE_KERNEL_SLUG = os.environ.get("KAGGLE_KERNEL_SLUG")

if not TELEGRAM_TOKEN:
    print("❌ TELEGRAM_TOKEN not set!")
    sys.exit(1)

# ========== تنظیمات ==========
COOLDOWN_SECONDS = 30
MAX_DAILY_MESSAGES = 20

# ========== دیتابیس در حافظه ==========
user_data = {}

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

def get_remaining(user_id: str) -> int:
    reset_if_needed(user_id)
    return MAX_DAILY_MESSAGES - get_user_data(user_id)["count"]

def add_history(user_id: str, user_msg: str, bot_response: str):
    data = get_user_data(user_id)
    data["history"].append({"user": user_msg, "bot": bot_response})
    if len(data["history"]) > 10:
        data["history"] = data["history"][-10:]

# ========== اتصال به کاگل با روش تضمینی ==========
def ask_kaggle(prompt: str) -> str:
    """
    ارسال سوال به کاگل با استفاده از Kaggle API
    """
    try:
        # روش ساده: از kaggle CLI استفاده کن
        cmd = [
            "kaggle", "kernels", "push",
            "-p", "/tmp/kernel",
            "--kernel-name", KAGGLE_KERNEL_SLUG,
            "--language", "python",
            "--kernel-type", "script"
        ]
        
        # کد پایتون برای اجرا روی کاگل
        code = f'''
import sys
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_NAME = "mistralai/Mistral-7B-Instruct-v0.1"
prompt = sys.argv[1] if len(sys.argv) > 1 else "سلام!"

print("⏳ لود کردن مدل...")
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_NAME,
    torch_dtype=torch.float16,
    device_map="auto"
)

formatted_prompt = f"[INST] {{prompt}} [/INST]"
inputs = tokenizer(formatted_prompt, return_tensors="pt").to("cuda")
outputs = model.generate(**inputs, max_new_tokens=256, temperature=0.7, pad_token_id=tokenizer.eos_token_id)
response = tokenizer.decode(outputs[0], skip_special_tokens=True)

if "[INST]" in response:
    response = response.split("[/INST]")[-1].strip()

print(response)
'''
        
        # ذخیره کد در فایل موقت
        os.makedirs("/tmp/kernel", exist_ok=True)
        with open("/tmp/kernel/main.py", "w") as f:
            f.write(code)
        
        # اجرا
        result = subprocess.run(
            cmd,
            env={**os.environ, "KAGGLE_USERNAME": KAGGLE_USERNAME},
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode == 0:
            return result.stdout.strip() or "پاسخی دریافت نشد!"
        else:
            return f"❌ خطا: {result.stderr}"
            
    except subprocess.TimeoutExpired:
        return "⏰ زمان اجرا تموم شد! دوباره تلاش کن."
    except Exception as e:
        return f"❌ خطا: {str(e)}"

# ========== دستورات ربات ==========
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    remaining = get_remaining(user_id)
    
    await update.message.reply_text(
        f"🤖 **Welcome to Mistral AI Bot!**\n\n"
        f"• I'm powered by **Mistral-7B** on Kaggle GPU.\n"
        f"• You have **{remaining}/{MAX_DAILY_MESSAGES}** messages today.\n"
        f"• You can send one message every **{COOLDOWN_SECONDS} seconds**.\n"
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
        f"💰 **Daily Limit:** {MAX_DAILY_MESSAGES} messages\n"
        f"⏰ **Cooldown:** {COOLDOWN_SECONDS} seconds\n"
        f"📊 **Remaining Today:** {remaining}/{MAX_DAILY_MESSAGES}\n\n"
        f"⚡ Powered by Kaggle GPU (Tesla T4 × 2)",
        parse_mode="Markdown"
    )

async def remaining(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    remaining = get_remaining(user_id)
    await update.message.reply_text(
        f"📊 **Remaining Messages:** {remaining}/{MAX_DAILY_MESSAGES}\n"
        f"⏰ Resets at midnight UTC.",
        parse_mode="Markdown"
    )

# ========== مدیریت پیام‌ها ==========
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
                f"You have used {MAX_DAILY_MESSAGES}/{MAX_DAILY_MESSAGES} today.\n"
                f"⏰ Please try again tomorrow.",
                parse_mode="Markdown"
            )
        return
    
    # ========== انیمیشن ==========
    progress_steps = [
        ("🤔 **Analyzing...**", 0.2),
        ("🧠 **Processing...**", 0.5),
        ("⚡ **Fetching response...**", 0.8),
        ("✨ **Almost there!**", 0.95)
    ]
    
    msg = await update.message.reply_text(
        "🤔 **Thinking...**\n`[░░░░░░░░░░░░░░░░░░░░] 0%`",
        parse_mode="Markdown"
    )
    
    for text, progress in progress_steps:
        bar_length = 20
        filled = int(bar_length * progress)
        bar = "█" * filled + "░" * (bar_length - filled)
        await msg.edit_text(
            f"{text}\n`[{bar}] {int(progress*100)}%`",
            parse_mode="Markdown"
        )
        await asyncio.sleep(0.8)
    
    # ========== گرفتن پاسخ از کاگل ==========
    response = ask_kaggle(prompt)
    
    increment_count(user_id)
    add_history(user_id, prompt, response)
    remaining = get_remaining(user_id)
    
    await msg.edit_text(
        f"💬 **Response:**\n{response}\n\n"
        f"📊 **Remaining Today:** {remaining}/{MAX_DAILY_MESSAGES}",
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
