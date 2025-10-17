from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/jira", summary="JIRA webhook receiver", description="Endpoint to receive JIRA webhooks (MVP placeholder).")
async def jira_webhook(payload: dict):
    # For MVP, accept and return OK
    return {"status": "ok"}
