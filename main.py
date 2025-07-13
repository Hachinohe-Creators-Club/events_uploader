import os
import logging
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse
import boto3
import requests
from datetime import datetime

# ================================
# ✅ まずロガーの設定と取得
# ================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ================================
# ✅ 環境変数
# ================================
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# ================================
# ✅ 設定チェック
# ================================
if not SLACK_BOT_TOKEN:
    logger.error("SLACK_BOT_TOKEN is not set! Check your Render environment variables.")
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    logger.error("AWS credentials are not set! Check your Render environment variables.")
if not S3_BUCKET_NAME:
    logger.error("S3_BUCKET_NAME is not set! Check your Render environment variables.")

# ================================
# ✅ boto3 クライアント
# ================================
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_DEFAULT_REGION,
)

# ================================
# ✅ FastAPI アプリ
# ================================
app = FastAPI()

class SlackRequest(BaseModel):
    token: str
    challenge: str
    type: str

def download_file(file_info):
    url = file_info["url_private"]
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        filename = file_info["name"]

        with open(filename, "wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded file: {filename}")

        today = datetime.now().strftime("%Y-%m-%d")
        s3_key = f"notices/{today}/{filename}"

        s3_client.upload_file(filename, S3_BUCKET_NAME, s3_key)
        logger.info(f"Uploaded to S3: s3://{S3_BUCKET_NAME}/{s3_key}")

    else:
        logger.error(f"Failed to download file: {response.status_code}")

@app.post("/slack/events")
async def slack_url_verification(request: Request):
    body = await request.json()

    if body.get("type") == "url_verification":
        logger.info('Slack URL verification request received.')
        return PlainTextResponse(content=body.get("challenge"), status_code=200)

    if body.get("type") == "event_callback":
        event = body.get("event")
        if event and event.get("type") == "message":
            subtype = event.get("subtype")
            if subtype and subtype not in ["file_share"]:
                logger.info(f"Ignored message with subtype: {subtype}")
                return {"status": "ignored"}

            text = event.get("text", "")
            files = event.get("files", [])

            logger.info(f"Text: {text}")
            for file_info in files:
                logger.info(f"File: {file_info['name']} ({file_info['mimetype']})")
                download_file(file_info)

    return {"status": "ok"}
