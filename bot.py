from fastapi import FastAPI, Request
import requests
import asyncio
import time
from datetime import datetime

app = FastAPI()

# تنظیمات
KAGGLE_URL = "https://publisher-mashed-trembling.ngrok-free.dev"  # این رو بعداً بروزرسانی کن
TELEGRAM_TOKEN = "8945063461:AAFru7ADhexqG8L8XxiXI8kXSoQ90B9bUWU"
LAST_ACTIVITY = time.time()
KAGGLE_ACTIVE = True

async def send_to_telegram(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    requests.post(url, json=payload)

@app.post("/webhook")
async def webhook(request: Request):
    global LAST_ACTIVITY, KAGGLE_ACTIVE
    
    data = await request.json()
    LAST_ACTIVITY = time.time()
    
    # استخراج پیام
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")
    
    if not chat_id or not text:
        return {"status": "ok"}
    
    print(f"دریافت پیام: {text}")
    
    # ارسال به Kaggle
    try:
        response = requests.post(
            f"{KAGGLE_URL}/infer",
            json={"message": text},
            timeout=30
        )
        result = response.json()
        ai_reply = result.get("response", "خطا در پردازش")
    except Exception as e:
        ai_reply = f"⚠️ Kaggle در دسترس نیست: {str(e)}"
    
    await send_to_telegram(chat_id, ai_reply)
    return {"status": "ok"}

@app.get("/")
async def home():
    return {"status": "Telegram Bot + Kaggle is running!"}

# Health check
@app.get("/health")
async def health():
    idle_time = int(time.time() - LAST_ACTIVITY)
    return {
        "status": "ok",
        "kaggle_url": KAGGLE_URL,
        "idle_seconds": idle_time
        }
