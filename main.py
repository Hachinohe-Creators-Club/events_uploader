import logging
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse

# ロガーの基本設定
logging.basicConfig(
    level=logging.INFO,  # ログレベル
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# アプリケーション用のロガーを取得
logger = logging.getLogger(__name__)

app = FastAPI()

class SlackRequest(BaseModel):
    token: str
    challenge: str
    type: str

@app.post("/slack/events")
async def slack_url_verification(request: Request):
    body = await request.json()

    # Slack の URL 検証リクエストかどうかを確認
    if body.get("type") == "url_verification":
        logging.info('Slack URL verification request received.')
        return PlainTextResponse(content=body.get("challenge"), status_code=200)

    # イベントコールバック
    if body.get("type") == "event_callback":
        event = body.get("event")
        if event and event.get("type") == "message":
            text = event.get("text")
            channel = event.get("channel")
            user = event.get("user")
            logger.info(f"Message event received! text: {text}, channel: {channel}, user: {user}")

            # ここで DB に保存したり他の処理をする
            # 必要なら Slack に返信したりもできる

    return {"status": "ok"}
