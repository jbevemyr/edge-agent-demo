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

SYSTEM_PROMPT = """You are a demo assistant for an internal support system.
You have tools to read application data and to escalate hard tasks to a stronger cloud model.

Rules:
- Prefer answering with tools: get_app_status, search_records, trigger_action when the user needs data or actions.
- Use ask_cloud_llm when the user needs long reasoning, nuanced writing, legal/medical style analysis, or you are unsure.
- After tool results, give a concise final answer to the user in the same language they used.
- When summarizing many records, you may call ask_cloud_llm with task and context built from tool outputs."""

TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_app_status",
            "description": "Get demo application health: case counts and recent actions.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_records",
            "description": "Search mock customer cases by optional text query and/or status filter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Optional substring for title, customer, or case id.",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["open", "overdue", "closed"],
                        "description": "Optional status filter.",
                    },
                },
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "trigger_action",
            "description": "Trigger a demo workflow action by id (e.g. notify-team, run-check).",
            "parameters": {
                "type": "object",
                "properties": {
                    "action_id": {
                        "type": "string",
                        "description": "Action identifier.",
                    }
                },
                "required": ["action_id"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_cloud_llm",
            "description": "Escalate a harder task to a larger cloud model. Pass structured context from prior tools.",
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

app = FastAPI(title="Demo Agent", version="0.1.0")


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
        if name == "get_app_status":
            data = await _http_get("/status")
            return json.dumps(data, ensure_ascii=False)
        if name == "search_records":
            params = {}
            if args.get("query"):
                params["query"] = args["query"]
            if args.get("status"):
                params["status"] = args["status"]
            data = await _http_get("/search", params=params)
            return json.dumps(data, ensure_ascii=False)
        if name == "trigger_action":
            aid = args.get("action_id", "")
            data = await _http_post("/action", {"action_id": aid})
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
