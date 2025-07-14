import os
import logging
import zipfile
import shutil
from fastapi import FastAPI, Request
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse
from github import Github
import boto3
import requests
from datetime import datetime
import pytz
from slugify import slugify

# ================================
# ロガー設定
# ================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ================================
# 環境変数
# ================================
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
AWS_DEFAULT_REGION = os.getenv("AWS_DEFAULT_REGION", "ap-northeast-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# ================================
# 設定チェック
# ================================
if not SLACK_BOT_TOKEN:
    logger.error("SLACK_BOT_TOKEN is not set! Check your Render environment variables.")
if not AWS_ACCESS_KEY_ID or not AWS_SECRET_ACCESS_KEY:
    logger.error("AWS credentials are not set! Check your Render environment variables.")
if not S3_BUCKET_NAME:
    logger.error("S3_BUCKET_NAME is not set! Check your Render environment variables.")

# ================================
# boto3 クライアント
# ================================
s3_client = boto3.client(
    "s3",
    aws_access_key_id=AWS_ACCESS_KEY_ID,
    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
    region_name=AWS_DEFAULT_REGION,
)

# ================================
# FastAPI アプリ
# ================================
app = FastAPI()

class SlackRequest(BaseModel):
    token: str
    challenge: str
    type: str


# ================================
# 日付関連
# ================================
def get_jst_today():
    jst = pytz.timezone('Asia/Tokyo')
    return datetime.now(jst).strftime("%Y-%m-%d")


# ================================
# GitHub 連携
# ================================
def upload_markdown_to_github(local_md_file: str, repo_path: str):
    """ローカルの markdown を GitHub にプッシュ"""
    github_token = os.getenv("GITHUB_TOKEN")
    github_repo = os.getenv("GITHUB_REPO")
    if not github_token or not github_repo:
        logger.error("GITHUB_TOKEN or GITHUB_REPO is not set!")
        return

    g = Github(github_token)
    repo = g.get_repo(github_repo)

    branch = "main"  # 必要なら `master` に
    commit_message = f"Add event: {os.path.basename(local_md_file)}"

    with open(local_md_file, "r", encoding="utf-8") as f:
        content = f.read()

    # プッシュ先のパス
    repo_file_path = f"events/{os.path.basename(local_md_file)}"

    try:
        contents = repo.get_contents(repo_file_path, ref=branch)
        # 既にあれば更新
        repo.update_file(
            path=repo_file_path,
            message=commit_message,
            content=content,
            sha=contents.sha,
            branch=branch
        )
        logger.info(f"Updated existing file: {repo_file_path}")

    except Exception:
        # なければ新規作成
        repo.create_file(
            path=repo_file_path,
            message=commit_message,
            content=content,
            branch=branch
        )
        logger.info(f"Created new file: {repo_file_path}")

# ================================
# ファイルを解凍して S3 にアップロード
# ================================
def download_and_extract_zip(file_info, title_text: str):
    url = file_info["url_private"]
    headers = {"Authorization": f"Bearer {SLACK_BOT_TOKEN}"}
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        zip_filename = file_info["name"]

        # タイムゾーンをJSTにする
        jst = pytz.timezone('Asia/Tokyo')
        today = datetime.now(jst).strftime("%Y-%m-%d")

        # 全角スペースを半角に
        title_part_normalized = title_text.replace('\u3000', ' ')

        title_slug = slugify(
            title_part_normalized,
            separator="-",
            regex_pattern=r"[^\w\s\u4e00-\u9fff\u3040-\u30ffーァ-ヶ一-龥]",  # 英数字+_+スペース+日本語を許可
            lowercase=False,
            allow_unicode=True
        )

        # 一時ZIP保存
        with open(zip_filename, "wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded ZIP file: {zip_filename}")

        # 解凍ディレクトリ
        extract_dir = "extracted"
        os.makedirs(extract_dir, exist_ok=True)

        with zipfile.ZipFile(zip_filename, "r") as zip_ref:
            zip_ref.extractall(extract_dir)
        logger.info(f"Extracted ZIP to: {extract_dir}")

        # 解凍したファイルをアップロード
        for root, dirs, files in os.walk(extract_dir):
            for file in files:
                local_path = os.path.join(root, file)

                if file.endswith(".md"):
                    upload_markdown_to_github(local_path, repo_path="events/")
                else:
                    relative_path = os.path.relpath(local_path, extract_dir)
                    s3_key = f"events/{today}/{title_slug}/{relative_path}"

                    s3_client.upload_file(local_path, S3_BUCKET_NAME, s3_key)
                    logger.info(f"Uploaded to S3: s3://{S3_BUCKET_NAME}/{s3_key}")

        # Cleanup
        os.remove(zip_filename)
        shutil.rmtree(extract_dir)

    else:
        logger.error(f"Failed to download file: {response.status_code}")

# ================================
# Slack エンドポイント
# ================================
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

            text = event.get("text", "untitled")
            files = event.get("files", [])

            logger.info(f"Text: {text}")
            for file_info in files:
                filename = file_info['name']
                basename, _ = os.path.splitext(filename)
                logger.info(f"File: {file_info['name']} ({file_info['mimetype']})")
                download_and_extract_zip(file_info, title_text=basename)

    return {"status": "ok"}

