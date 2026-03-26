# Edge agent demo

Three containers that show how a **local LLM** (typically **vLLM** in CI, or **Ollama** on your site) can orchestrate **tool calls** against a **warehouse operations API**, and optionally escalate to a **cloud LLM** when the model invokes the `ask_cloud_llm` tool (a stand-in for heavier **core** analysis, similar to the edge/core split described in Cisco's Secure AI Factory narrative).

**Disclaimer:** This repository is an independent reference demo. It is **not** an official Cisco product, does not integrate Vaidio, Aible, Cisco AI Defense, or Intersight, and uses **synthetic** inventory and events only.

**Story alignment:** The mock app models **edge warehouse operations**: inventory, shipment cutoffs, and operational events including **synthetic vision-style** alerts. That mirrors the [intelligent warehouse / multi-agent edge](https://blogs.cisco.com/datacenter/cisco-gives-its-secure-ai-factory-with-nvidia-a-secure-multi-agent-edge-up?ccid=cc006075) themes from Cisco's blog (March 2026).

| Service | Role | Default port |
|---------|------|--------------|
| **app** | Warehouse Operations API (inventory, events, shipments) | 8001 |
| **agent** | Chat API, tool loop, calls app + local/cloud models | 8002 |
| **local-llm** | vLLM (OpenAI-compatible HTTP API). Optional: use **Ollama** on the site instead; see [Using Ollama](#using-ollama-instead-of-the-vllm-container). | 8000 |

**Flow (short):** The user sends a message to the agent. The local model may request **tools**; the agent executes them (HTTP to the app, or cloud for `ask_cloud_llm`) and feeds results back until the model returns a final text reply. A small web UI is served at the agent root URL.

For the full REST surface of the app and how tools map to HTTP, see [Warehouse Operations API and agent integration](#warehouse-operations-api-and-agent-integration).

## Requirements

- **Container images** from **GHCR**, built by this repo's CI (three images, one shared version tag).
- **NVIDIA GPU** on hosts running **local-llm** (vLLM), unless you use **Ollama** elsewhere with its own hardware rules.
- Enough **RAM/VRAM**; vLLM’s first start downloads the model from Hugging Face (can take many minutes). Ollama uses its own model store (`ollama pull`).

Optional: `curl` and `jq` for formatted JSON from `scripts/demo.sh`.

## Run on Avassa

1. **Application spec:** see **[Applications | Avassa Docs](https://docs.avassa.io/how-to/applications)**. Start from [`avassa/application.example.yaml`](avassa/application.example.yaml).
2. **Deployment:** see **[Application Deployment | Avassa Docs](https://docs.avassa.io/how-to/deploying-applications)** and [`avassa/deployment.example.yaml`](avassa/deployment.example.yaml).

**Mapping this demo to Avassa:**

| Concern | Notes |
|--------|--------|
| **Images** | Three GHCR images, **same** tag. |
| **Environment** | Agent: `APP_URL`, `LOCAL_LLM_BASE`, `LOCAL_MODEL`; optional `OPENAI_API_KEY` / `CLOUD_MODEL`. |
| **Internal URLs** | [Application networks](https://docs.avassa.io/how-to/applications-and-deployments/configuring-application-networks). |
| **GPU** | [GPU passthrough](https://docs.avassa.io/how-to/applications#request-gpu-passthrough) for **local-llm**. |
| **Model cache** | [Ephemeral](https://docs.avassa.io/how-to/applications#add-ephemeral-volume-configuration-to-a-service) / [persistent](https://docs.avassa.io/how-to/applications#add-persistent-volume-configuration-to-a-service) volume for Hugging Face cache. |
| **Ingress** | TCP **8002** on agent ([ingress](https://docs.avassa.io/how-to/applications#add-ingress-ip-configuration-to-a-service)); optional **8001** for OpenAPI. |
| **Outbound** | If using `OPENAI_API_KEY`, allow HTTPS to OpenAI ([outbound](https://docs.avassa.io/how-to/applications#allow-unrestricted-outbound-network-access-for-a-service)). |
| **Secrets** | [Strongbox](https://docs.avassa.io/how-to/applications#add-strongbox-secrets-to-an-application). |

### Using Ollama instead of the vLLM container

If **Ollama** already runs on the site, you do **not** need the **`local-llm`** service from this repo. Deploy only **`app`** + **`agent`** (see [`avassa/application.ollama.example.yaml`](avassa/application.ollama.example.yaml)) and point the agent at Ollama’s [OpenAI-compatible API](https://github.com/ollama/ollama/blob/main/docs/openai.md).

| Setting | Value |
|---------|--------|
| `LOCAL_LLM_BASE` | Base URL including **`/v1`**, e.g. `http://ollama:11434/v1` or whatever hostname/port your site uses for Ollama. |
| `LOCAL_MODEL` | An Ollama **model name** you have pulled on that instance (e.g. `llama3.2`, `qwen2.5`, `mistral`). Must match `ollama list` on the server. |
| `LOCAL_LLM_API_KEY` | Ollama usually ignores this; any non-empty placeholder (e.g. `ollama`) is fine for the Python OpenAI client. |

**Networking:** The **agent** container must be able to open **HTTP** to Ollama’s API port (default **11434**) on the application or site network. If Ollama is another Avassa application, use the hostname your platform assigns for service discovery.

**Tool calling:** This demo relies on **function / tool** calls. Use an Ollama model that supports tools well enough for your hardware; small models may omit or misuse tools.

**CI images:** You can still build only **`app`** and **`agent`** from GHCR; skip the **`local-llm`** image on sites that use Ollama.

### Deploying to edge sites

| Topic | Link |
|--------|------|
| **Placement** | [Labels](https://docs.avassa.io/how-to/deploying-applications#placing-applications-based-on-labels) |
| **Rolling** | [Rolling deployments](https://docs.avassa.io/how-to/deploying-applications#rolling-deployments) |
| **Canary** | [Canary deployments](https://docs.avassa.io/how-to/deploying-applications#canary-deployments) |
| **New sites** | [Redeploy](https://docs.avassa.io/how-to/deploying-applications#adding-sites-to-a-deployment) |

## Container images (CI to GHCR)

Tag `v*` builds:

- `ghcr.io/<owner>/<repo>/app:<tag>`
- `ghcr.io/<owner>/<repo>/agent:<tag>`
- `ghcr.io/<owner>/<repo>/local-llm:<tag>`

## Environment variables

Set on containers in the Avassa spec (or map from vault into `env`).

### Agent

| Variable | Typical value | Description |
|----------|---------------|-------------|
| `APP_URL` | `http://app:8001` | Warehouse API base URL. |
| `LOCAL_LLM_BASE` | `http://local-llm:8000/v1` | OpenAI-compatible chat base URL (**vLLM**). For **Ollama**, e.g. `http://ollama:11434/v1`. |
| `LOCAL_MODEL` | `Qwen/Qwen2.5-0.5B-Instruct` | Model id sent to the API. For vLLM, match the server; for Ollama, use a pulled tag (e.g. `llama3.2`). |
| `LOCAL_LLM_API_KEY` | `local` | Placeholder for OpenAI client. |
| `MAX_TOOL_ROUNDS` | `12` | Tool round limit. |
| `OPENAI_API_KEY` | *(secret)* | Optional; `ask_cloud_llm` + fallback. |
| `CLOUD_MODEL` | `gpt-4o-mini` | Cloud model name. |

See [`.env.example`](.env.example) for a short checklist.

### local-llm

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | If using a gated Hugging Face model. |

## Warehouse Operations API and agent integration

### App service (REST API)

The **app** container runs a FastAPI **Warehouse Operations API** ([`app/main.py`](app/main.py)). It holds **in-memory** synthetic data: warehouses, inventory lines, operational events (including rows with `source: synthetic_vision`), and pending shipments. The app **does not** call the agent or any LLM; it is a plain HTTP backend.

Business routes live under **`/v1/...`**. When port **8001** is exposed, interactive docs are at **`/docs`**.

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness; includes `service: warehouse-ops`. |
| `GET` | `/v1/operations/summary` | Roll-up: open events by severity, SKUs below reorder, pending shipments, next cutoffs, recent acknowledge actions. |
| `GET` | `/v1/events` | Query params: `severity`, `type` (event type: `stockout_risk`, `low_stock`, `safety_hold`), `warehouse_id`, `status` (`open` / `acknowledged`), `query` (text in title, event id, sku). Response: `count`, `events`. |
| `GET` | `/v1/inventory` | Query params: `warehouse_id`, `sku`, `below_reorder` (boolean), `query` (sku or description). Response: `count`, `lines`. |
| `GET` | `/v1/warehouses/{warehouse_id}` | One warehouse: metadata, counts, **open** events for that site, pending shipments. `404` if the id is unknown. |
| `POST` | `/v1/events/{event_id}/acknowledge` | Marks the event acknowledged and timestamps it. Optional JSON body: `{"note": "..."}`. Idempotent if already acknowledged. |

### How the agent uses the app

The **agent** ([`agent/main.py`](agent/main.py)) exposes **`POST /chat`** and a small UI on **`/`**. It calls the **local LLM** with OpenAI-style **function tools**. The inference server **does not** call the warehouse app; only the agent does, after the model returns `tool_calls`.

1. The **user** sends natural language to the agent (`/chat` or UI).
2. The agent forwards the conversation and tool definitions to the **local LLM** (`LOCAL_LLM_BASE`, `LOCAL_MODEL`).
3. When the model returns **tool calls**, the agent runs **`execute_tool`** in Python and, for warehouse tools, sends **HTTP** requests to **`APP_URL`** (for example `http://app:8001` on the application network) using `httpx`.
4. Each tool result is returned to the model as a **tool** message. This repeats up to **`MAX_TOOL_ROUNDS`** until the model emits a final assistant message.
5. **`ask_cloud_llm`** is different: it invokes the **cloud** OpenAI API with `task` and `context`, not the app. It needs **`OPENAI_API_KEY`** (optional in your deployment).

**Tool name to HTTP mapping:**

| Agent tool (for the LLM) | App request |
|--------------------------|-------------|
| `get_warehouse_summary` | `GET /v1/operations/summary` |
| `query_events` | `GET /v1/events` (maps `event_type` to query param `type`) |
| `query_inventory` | `GET /v1/inventory` (`below_reorder: true` becomes `below_reorder=true`) |
| `get_warehouse_detail` | `GET /v1/warehouses/{warehouse_id}` |
| `acknowledge_event` | `POST /v1/events/{event_id}/acknowledge` with optional `{"note": ...}` |

The **`/chat`** response includes **`reply`** (assistant text) and **`audit`** (tool names and short previews) for demos.

## Demo script

```bash
./scripts/demo.sh
```

Override hosts if needed (`LLM_URL` is vLLM port **8000** by default; for **Ollama** use port **11434**):

```bash
APP_URL=http://<app-host>:8001 \
LLM_URL=http://<llm-host>:8000 \
AGENT_URL=http://<agent-host>:8002 \
./scripts/demo.sh
```

## Suggested talking points (e.g. for blog authors / stakeholders)

1. **Edge vs core:** Local SLM + tools at the edge; `ask_cloud_llm` illustrates when **core-scale** reasoning might run (no real data lake here).  
2. **IT/OT bridge:** Synthetic **vision-sourced** events (`source: synthetic_vision`) feeding the same REST API an agent would call.  
3. **Operational loop:** Summary, then query critical events, then optional **acknowledge** (operator action).  
4. **Security posture:** Mention **Cisco AI Defense** and runtime guardrails from the [blog](https://blogs.cisco.com/datacenter/cisco-gives-its-secure-ai-factory-with-nvidia-a-secure-multi-agent-edge-up?ccid=cc006075) as the **production** target; this repo stays a minimal agent + API slice.  
5. **Deployment:** Three images on **Avassa** with GPU for vLLM, or **two** images (**app** + **agent**) if inference is **Ollama** on the site.

## Troubleshooting

- **Agent not ready:** Wait for the local model (vLLM download/load or Ollama ready with the model pulled).  
- **GPU:** Confirm **local-llm** (vLLM) has a GPU, or size Ollama appropriately on the site.  
- **Weak tool use:** Use a larger model; set `LOCAL_MODEL` to match the server (vLLM model id or Ollama model name).  
- **Ollama connection errors:** Check `LOCAL_LLM_BASE` ends with `/v1`, port **11434**, and network path from **agent** to Ollama.
