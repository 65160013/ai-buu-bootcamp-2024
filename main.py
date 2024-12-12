import requests
from io import BytesIO
from PIL import Image
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (Configuration,
                                  ApiClient,
                                  MessagingApi,
                                  ReplyMessageRequest,
                                  TextMessage)
from linebot.v3.webhooks import (MessageEvent,
                                 TextMessageContent,
                                 ImageMessageContent)
from linebot.v3.exceptions import InvalidSignatureError
import openai  # ใช้ openai แทน gemini

app = FastAPI()

# ข้อมูล token และ channel secret สำหรับ LINE
ACCESS_TOKEN = "+OiZWbE5ZDDY8claJxoan3K3kZrkHr8UL1ZiwhwU4aehPvxxZlpTSmotFyFN4oMQ05xlDvm3odElx/xdt4wwscoP4J1WxVMTSrzKl+BnxIXOrVxx3b8TxkJUlXHLzriXeGXAVCdo0lkn4w7gcTqBhwdB04t89/1O/w1cDnyilFU="
CHANNEL_SECRET = "535ba27bc0bcd3edb3b968a34b4c2ed5"

# ข้อมูล OpenAI API key
OPENAI_API_KEY = "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"  # ใส่ API Key ของ OpenAI ที่ได้จาก https://platform.openai.com/account/api-keys

# การเชื่อมต่อ และตั้งค่าข้อมูลเพื่อเรียกใช้งาน LINE Messaging API
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(channel_secret=CHANNEL_SECRET)

# การตั้งค่า OpenAI API Key
openai.api_key = OPENAI_API_KEY


# Endpoint สำหรับการสร้าง Webhook
@app.post('/message')
async def message(request: Request):
    # การตรวจสอบ headers จากการขอเรียกใช้บริการว่ามาจากทาง LINE Platform จริง
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        raise HTTPException(
            status_code=400, detail="X-Line-Signature header is missing")

    # ข้อมูลที่ส่งมาจาก LINE Platform
    body = await request.body()

    try:
        # เรียกใช้งาน Handler เพื่อจัดข้อความจาก LINE Platform
        handler.handle(body.decode("UTF-8"), signature)
    except InvalidSignatureError:
        raise HTTPException(status_code=400, detail="Invalid signature")


# Function สำหรับจัดการข้อมูลที่ส่งมากจาก LINE Platform
@handler.add(MessageEvent, message=(TextMessageContent, ImageMessageContent))
def handle_message(event: MessageEvent):
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        # ตรวจสอบ Message ว่าเป็นประเภทข้อความ Text
        if isinstance(event.message, TextMessageContent):
            user_message = event.message.text

            # นำข้อความส่งไปยัง OpenAI API เพื่อให้ ChatGPT ประมวลผล
            try:
                chatgpt_response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # หรือสามารถใช้ "gpt-4" หากมีสิทธิ์
                    messages=[{"role": "user", "content": user_message}]
                )
                gemini_response = chatgpt_response.choices[0].message['content']
            except Exception as e:
                gemini_response = "เกิดข้อผิดพลาดในการติดต่อกับ ChatGPT, กรุณาลองใหม่อีกครั้ง"

            # Reply ข้อมูลกลับไปยัง LINE
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    replyToken=event.reply_token,
                    messages=[TextMessage(text=gemini_response)]
                )
            )

        # ตรวจสอบ Message ว่าเป็นประเภทข้อความ Image
        if isinstance(event.message, ImageMessageContent):
            # การขอข้อมูลภาพจาก LINE Service
            headers = {"Authorization": f"Bearer {ACCESS_TOKEN}"}
            url = f"https://api-data.line.me/v2/bot/message/{event.message.id}/content"
            try:
                response = requests.get(url, headers=headers, stream=True)
                response.raise_for_status()
                image_data = BytesIO(response.content)
                image = Image.open(image_data)
            except Exception as e:
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        replyToken=event.reply_token,
                        messages=[TextMessage(text="เกิดข้อผิดพลาด, กรุณาลองใหม่อีกครั้ง🙏🏻")]
                    )
                )
                return

            try:
                # ส่งข้อมูลภาพไปยัง ChatGPT เพื่อขอคำอธิบาย
                chatgpt_response = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",  # หรือสามารถใช้ "gpt-4" หากมีสิทธิ์
                    messages=[
                        {"role": "user", "content": "อธิบายรูปภาพนี้"},
                        {"role": "user", "content": "image_url_placeholder"}  # เพิ่ม URL หรือข้อมูลภาพจริง
                    ]
                )
                response_text = chatgpt_response.choices[0].message['content']
            except Exception as e:
                response_text = f"เกิดข้อผิดพลาด, ไม่สามารถประมวลผลรูปภาพได้"

            # Reply ข้อมูลกลับไปยัง LINE
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    replyToken=event.reply_token, messages=[TextMessage(text=response_text)]
                )
            )


if __name__ == "__main__":
    uvicorn.run("main:app",
                port=8000,
                host="0.0.0.0")
