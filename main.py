import os
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

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

if not SLACK_BOT_TOKEN:
    logger.error("SLACK_BOT_TOKEN is not set! Check your Render environment variables.")

class SlackRequest(BaseModel):
    token: str
    challenge: str
    type: str

def download_file(file_info):
    """Slack の添付ファイルを認証付きでダウンロード"""
    url = file_info["url_private"]
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        filename = file_info["name"]
        with open(filename, "wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded file: {filename}")
    else:
        logger.error(f"Failed to download file: {response.status_code}")

@app.post("/slack/events")
async def slack_url_verification(request: Request):
    body = await request.json()

    # Slack の URL 検証（必須）
    if body.get("type") == "url_verification":
        logger.info('Slack URL verification request received.')
        return PlainTextResponse(content=body.get("challenge"), status_code=200)

    # イベントコールバック
    if body.get("type") == "event_callback":
        event = body.get("event")
        if event and event.get("type") == "message" and "subtype" not in event:
            text = event.get("text", "")
            channel = event.get("channel")
            user = event.get("user")
            logger.info(f"Message event received! text: {text}, channel: {channel}, user: {user}")

            # 添付ファイルがあれば取得
            files = event.get("files", [])
            for file_info in files:
                logger.info(f"Attached file: {file_info['name']} ({file_info['mimetype']})")
                logger.info(f"File URL: {file_info['url_private']}")
                download_file(file_info)

            # 必要に応じてDB保存や他の処理を追加OK

    return {"status": "ok"}
