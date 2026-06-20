from fastapi import FastAPI, Request
import requests
import time

app = FastAPI(title="Telegram Kaggle Bot")

# === تنظیمات ===
KAGGLE_URL = "https://publisher-mashed-trembling.ngrok-free.dev"
TELEGRAM_TOKEN = "8945063461:AAFru7ADhexqG8L8XxiXI8kXSoQ90B9bUWU"

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        message = data.get("message", {})
        chat_id = message.get("chat", {}).get("id")
        text = message.get("text", "").strip()

        if not chat_id or not text:
            return {"status": "ok"}

        print(f"📨 پیام: {text}")

        # فرستادن به Kaggle
        try:
            resp = requests.post(f"{KAGGLE_URL}/infer", 
                               json={"message": text}, 
                               timeout=30)
            result = resp.json()
            reply = result.get("response", "خطا در Kaggle")
        except Exception as e:
            reply = f"⚠️ Kaggle در دسترس نیست\n{str(e)[:80]}"

        # ارسال جواب به تلگرام
        tg_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(tg_url, json={"chat_id": chat_id, "text": reply})
        
        return {"status": "ok"}
    
    except Exception as e:
        print("Error:", e)
        return {"status": "error"}

@app.get("/")
async def home():
    return {"status": "✅ Bot is running!", "kaggle_url": KAGGLE_URL}

@app.get("/health")
async def health():
    return {"status": "ok", "kaggle_url": KAGGLE_URL, "idle_seconds": 0}
