from fastapi import FastAPI, Request
import requests

app = FastAPI()

KAGGLE_URL = " https://publisher-mashed-trembling.ngrok-free.dev"  # این آدرس رو عوض کن
TELEGRAM_TOKEN = "8945063461:AAFru7ADhexqG8L8XxiXI8kXSoQ90B9bUWU"

@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"status": "ok"}

    try:
        resp = requests.post(f"{KAGGLE_URL}/infer", json={"message": text}, timeout=30)
        reply = resp.json().get("response", "خطا")
    except:
        reply = "⚠️ Kaggle در دسترس نیست"

    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": chat_id, "text": reply}
    )
    
    return {"status": "ok"}
