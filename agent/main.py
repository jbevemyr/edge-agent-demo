"""Orchestration agent: local LLM + tools + optional cloud escalation."""

import json
import logging
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("agent")

APP_URL = os.environ.get("APP_URL", "http://localhost:8001").rstrip("/")
LOCAL_BASE = os.environ.get("LOCAL_LLM_BASE", "http://localhost:8000/v1").rstrip("/")
LOCAL_MODEL = os.environ.get("LOCAL_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
CLOUD_MODEL = os.environ.get("CLOUD_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
MAX_TOOL_ROUNDS = int(os.environ.get("MAX_TOOL_ROUNDS", "12"))

SYSTEM_PROMPT = """You are an edge warehouse operations assistant. The warehouse operations API holds inventory,
operational events (including synthetic vision-style alerts), and shipment cutoffs.

Use tools to fetch real data before answering. For long business impact analysis, executive-style summaries,
or multi-step reasoning across many facts, call ask_cloud_llm with a clear task and compact context from tools.

Rules:
- Prefer get_warehouse_summary, query_events, query_inventory, get_warehouse_detail, acknowledge_event when the user needs data or to acknowledge an event.
- Use ask_cloud_llm for revenue/shipping impact narratives, detailed mitigation plans, or when the user explicitly wants the "core" or cloud model.
- After tool results, answer concisely in the same language the user used."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_warehouse_summary",
            "description": "Aggregated warehouse ops snapshot: open events by severity, SKUs below reorder, pending shipments, next cutoffs.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_events",
            "description": "List operational events (stockout_risk, low_stock, safety_hold) with optional filters.",
            "parameters": {
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "warning", "info"],
                        "description": "Optional severity filter.",
                    },
                    "event_type": {
                        "type": "string",
                        "enum": ["stockout_risk", "low_stock", "safety_hold"],
                        "description": "Optional event type filter.",
                    },
                    "warehouse_id": {
                        "type": "string",
                        "description": "Optional warehouse id e.g. WH-EU-01.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "acknowledged"],
                        "description": "Optional status filter.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Optional text search in title, event id, or sku.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_inventory",
            "description": "Query inventory lines by warehouse, sku, below reorder, or text search.",
            "parameters": {
                "type": "object",
                "properties": {
                    "warehouse_id": {"type": "string", "description": "Optional warehouse id."},
                    "sku": {"type": "string", "description": "Exact SKU if known."},
                    "below_reorder": {
                        "type": "boolean",
                        "description": "If true, only lines under reorder point.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Substring match on sku or description.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_warehouse_detail",
            "description": "Detail for one warehouse: metadata, open events, pending shipments, reorder counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "warehouse_id": {
                        "type": "string",
                        "description": "Warehouse id e.g. WH-EU-01.",
                    }
                },
                "required": ["warehouse_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "acknowledge_event",
            "description": "Mark an operational event as acknowledged (operator workflow).",
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "Event id e.g. EV-2041.",
                    },
                    "note": {
                        "type": "string",
                        "description": "Optional operator note.",
                    },
                },
                "required": ["event_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_cloud_llm",
            "description": "Escalate a harder task to a larger cloud model (stand-in for core data-center analysis). Pass structured context from prior tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task": {
                        "type": "string",
                        "description": "What the cloud model should produce.",
                    },
                    "context": {
                        "type": "string",
                        "description": "Relevant facts JSON or bullet text from tools.",
                    },
                },
                "required": ["task", "context"],
                "additionalProperties": False,
            },
        },
    },
]

app = FastAPI(title="Warehouse Edge Agent", version="0.2.0")


def _local_client() -> OpenAI:
    return OpenAI(base_url=LOCAL_BASE, api_key=os.environ.get("LOCAL_LLM_API_KEY", "local"))


def _cloud_client() -> OpenAI | None:
    if not OPENAI_API_KEY:
        return None
    return OpenAI(api_key=OPENAI_API_KEY)


async def _http_get(path: str, params: dict[str, Any] | None = None) -> Any:
    url = f"{APP_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


async def _http_post(path: str, json_body: dict[str, Any]) -> Any:
    url = f"{APP_URL}{path}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=json_body)
        r.raise_for_status()
        return r.json()


async def execute_tool(name: str, arguments: str) -> str:
    try:
        args = json.loads(arguments) if arguments else {}
    except json.JSONDecodeError:
        return json.dumps({"error": "invalid_json_arguments", "raw": arguments[:500]})

    try:
        if name == "get_warehouse_summary":
            data = await _http_get("/v1/operations/summary")
            return json.dumps(data, ensure_ascii=False)
        if name == "query_events":
            params = {}
            if args.get("severity"):
                params["severity"] = args["severity"]
            if args.get("event_type"):
                params["type"] = args["event_type"]
            if args.get("warehouse_id"):
                params["warehouse_id"] = args["warehouse_id"]
            if args.get("status"):
                params["status"] = args["status"]
            if args.get("query"):
                params["query"] = args["query"]
            data = await _http_get("/v1/events", params=params)
            return json.dumps(data, ensure_ascii=False)
        if name == "query_inventory":
            params = {}
            if args.get("warehouse_id"):
                params["warehouse_id"] = args["warehouse_id"]
            if args.get("sku"):
                params["sku"] = args["sku"]
            if args.get("below_reorder") is True:
                params["below_reorder"] = "true"
            if args.get("query"):
                params["query"] = args["query"]
            data = await _http_get("/v1/inventory", params=params)
            return json.dumps(data, ensure_ascii=False)
        if name == "get_warehouse_detail":
            wid = args.get("warehouse_id", "")
            data = await _http_get(f"/v1/warehouses/{wid}")
            return json.dumps(data, ensure_ascii=False)
        if name == "acknowledge_event":
            eid = args.get("event_id", "")
            note = args.get("note")
            body: dict[str, Any] = {}
            if note is not None:
                body["note"] = note
            data = await _http_post(f"/v1/events/{eid}/acknowledge", body)
            return json.dumps(data, ensure_ascii=False)
        if name == "ask_cloud_llm":
            cloud = _cloud_client()
            if cloud is None:
                return json.dumps(
                    {
                        "error": "cloud_not_configured",
                        "hint": "Set OPENAI_API_KEY on the agent service to enable escalation.",
                    },
                    ensure_ascii=False,
                )
            task = str(args.get("task", ""))
            ctx = str(args.get("context", ""))
            user_msg = f"Task:\n{task}\n\nContext:\n{ctx}"
            resp = cloud.chat.completions.create(
                model=CLOUD_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful analyst. Answer clearly using only the provided context.",
                    },
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
            )
            text = resp.choices[0].message.content or ""
            return json.dumps({"cloud_model": CLOUD_MODEL, "answer": text}, ensure_ascii=False)
        return json.dumps({"error": "unknown_tool", "name": name})
    except httpx.HTTPStatusError as e:
        return json.dumps(
            {"error": "app_http_error", "status": e.response.status_code, "detail": e.response.text[:500]}
        )
    except Exception as e:
        log.exception("tool_failed name=%s", name)
        return json.dumps({"error": str(type(e).__name__), "message": str(e)})


async def run_agent_turn(user_message: str) -> tuple[str, list[dict[str, Any]]]:
    local = _local_client()
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    audit: list[dict[str, Any]] = []

    rounds = 0
    while rounds < MAX_TOOL_ROUNDS:
        rounds += 1
        try:
            completion = local.chat.completions.create(
                model=LOCAL_MODEL,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                temperature=0.2,
            )
        except Exception as e:
            log.exception("local_llm_call_failed")
            audit.append({"type": "error", "where": "local_llm", "message": str(e)})
            if _cloud_client() is not None:
                cloud = _cloud_client()
                assert cloud is not None
                resp = cloud.chat.completions.create(
                    model=CLOUD_MODEL,
                    messages=[
                        {"role": "system", "content": "Local model failed. Help the user briefly."},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                )
                return resp.choices[0].message.content or "", audit
            raise

        choice = completion.choices[0]
        msg = choice.message
        if getattr(msg, "tool_calls", None):
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "{}",
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                raw_args = tc.function.arguments or "{}"
                audit.append({"type": "tool_call", "name": name, "arguments": raw_args[:2000]})
                result = await execute_tool(name, raw_args)
                audit.append({"type": "tool_result", "name": name, "preview": result[:500]})
                messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})
            continue

        text = (msg.content or "").strip()
        if text:
            return text, audit
        return "(empty model response)", audit

    return "Stopped: too many tool rounds.", audit


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=16000)


class ChatResponse(BaseModel):
    reply: str
    audit: list[dict[str, Any]] = Field(default_factory=list)


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    reply, audit = await run_agent_turn(body.message)
    return ChatResponse(reply=reply, audit=audit)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(static_dir):
    app.mount("/ui", StaticFiles(directory=static_dir, html=True), name="ui")


@app.get("/")
def root() -> FileResponse:
    index = os.path.join(static_dir, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    raise HTTPException(status_code=404, detail="UI not found")
