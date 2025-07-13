from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse

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
        return PlainTextResponse(content=body.get("challenge"), status_code=200)
    
    # その他のリクエストには 200 OK を返す（必要に応じて他の処理をここで実装）
    return {"message": "event received"}
