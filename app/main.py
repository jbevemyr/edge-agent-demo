"""Demo business application: mock customer cases and actions."""

from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

app = FastAPI(title="Demo App", version="0.1.0")

# In-memory mock data for the demo
MOCK_CASES: list[dict[str, Any]] = [
    {
        "id": "C-1001",
        "customer": "Acme AB",
        "status": "open",
        "title": "VPN access request",
        "due": (datetime.now(timezone.utc) + timedelta(days=5)).date().isoformat(),
    },
    {
        "id": "C-1002",
        "customer": "Nordic Tech",
        "status": "overdue",
        "title": "Firewall rule review",
        "due": (datetime.now(timezone.utc) - timedelta(days=3)).date().isoformat(),
    },
    {
        "id": "C-1003",
        "customer": "CityNet",
        "status": "overdue",
        "title": "Incident follow-up",
        "due": (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat(),
    },
]

ACTION_LOG: list[dict[str, Any]] = []


class ActionRequest(BaseModel):
    action_id: str = Field(..., description="Identifier for the action to run")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/status")
def get_status() -> dict[str, Any]:
    overdue = sum(1 for c in MOCK_CASES if c["status"] == "overdue")
    return {
        "service": "demo-app",
        "cases_total": len(MOCK_CASES),
        "cases_overdue": overdue,
        "last_actions": ACTION_LOG[-5:],
    }


@app.get("/search")
def search_records(
    query: str | None = Query(None, description="Free-text search in title/customer"),
    status: str | None = Query(None, description="Filter: open, overdue, closed"),
) -> dict[str, Any]:
    rows = list(MOCK_CASES)
    if status:
        rows = [c for c in rows if c["status"] == status.lower()]
    if query:
        q = query.lower()
        rows = [
            c
            for c in rows
            if q in c["title"].lower() or q in c["customer"].lower() or q in c["id"].lower()
        ]
    return {"count": len(rows), "records": rows}


@app.post("/action")
def trigger_action(body: ActionRequest) -> dict[str, Any]:
    entry = {
        "action_id": body.action_id,
        "at": datetime.now(timezone.utc).isoformat(),
        "result": "accepted",
    }
    ACTION_LOG.append(entry)
    return {"ok": True, "detail": entry}


@app.get("/cases/{case_id}")
def get_case(case_id: str) -> dict[str, Any]:
    for c in MOCK_CASES:
        if c["id"] == case_id:
            return c
    raise HTTPException(status_code=404, detail="Case not found")
