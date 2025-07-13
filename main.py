import os
import logging
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse

# Slack Bot Token
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

if not SLACK_BOT_TOKEN:
    logger.error("SLACK_BOT_TOKEN is not set! Check your Render environment variables.")

# AWS
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")  # デフォルト設定も可
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# 設定チェック
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    logger.error("AWS credentials are not set! Check your Render environment variables.")

if not S3_BUCKET_NAME:
    logger.error("S3_BUCKET_NAME is not set! Check your Render environment variables.")

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
        if event and event.get("type") == "message":
            subtype = event.get("subtype")
            # bot_message は除外、file_share はOK
            if subtype and subtype not in ["file_share"]:
                logger.info(f"Ignored message with subtype: {subtype}")
                return {"status": "ignored"}

            text = event.get("text", "")
            files = event.get("files", [])

            logger.info(f"Text: {text}")
            for file_info in files:
                logger.info(f"File: {file_info['name']} ({file_info['mimetype']})")

            # ここでファイルをダウンロード
            # 解析処理
            # 外部サービスへ送信

    return {"status": "ok"}
