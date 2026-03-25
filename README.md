# Edge agent demo

All documentation, API descriptions, and UI copy in this repository are **English only**.

Three containers that show how a **local LLM** (vLLM) can orchestrate **tool calls** against a **warehouse operations API**, and optionally escalate to a **cloud LLM** when the model invokes the `ask_cloud_llm` tool (a stand-in for heavier **core** analysis, similar to the edge/core split described in Cisco's Secure AI Factory narrative).

**Disclaimer:** This repository is an independent reference demo. It is **not** an official Cisco product, does not integrate Vaidio, Aible, Cisco AI Defense, or Intersight, and uses **synthetic** inventory and events only.

**Story alignment:** The mock app models **edge warehouse operations**: inventory, shipment cutoffs, and operational events including **synthetic vision-style** alerts. That mirrors the [intelligent warehouse / multi-agent edge](https://blogs.cisco.com/datacenter/cisco-gives-its-secure-ai-factory-with-nvidia-a-secure-multi-agent-edge-up?ccid=cc006075) themes from Cisco's blog (March 2026).

| Service | Role | Default port |
|---------|------|--------------|
| **app** | Warehouse Operations API (inventory, events, shipments) | 8001 |
| **agent** | Chat API, tool loop, calls app + local/cloud models | 8002 |
| **local-llm** | vLLM with an OpenAI-compatible HTTP API | 8000 |

**Flow:** The user sends a message to the agent. The local model may call tools (`get_warehouse_summary`, `query_events`, `query_inventory`, `get_warehouse_detail`, `acknowledge_event`, `ask_cloud_llm`). The agent executes those tools and returns the final reply. A small web UI is served at the agent root URL.

## Requirements

- **Container images** from **GHCR**, built by this repo's CI (three images, one shared version tag).
- **NVIDIA GPU** on hosts running **local-llm**, as configured on your edge platform (on Avassa: [GPU passthrough](https://docs.avassa.io/how-to/applications#request-gpu-passthrough)).
- Enough **RAM/VRAM**; the first start downloads the model from Hugging Face (can take many minutes).

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
| `LOCAL_LLM_BASE` | `http://local-llm:8000/v1` | vLLM OpenAI-compatible base. |
| `LOCAL_MODEL` | `Qwen/Qwen2.5-0.5B-Instruct` | Must match vLLM startup. |
| `LOCAL_LLM_API_KEY` | `local` | Placeholder for OpenAI client. |
| `MAX_TOOL_ROUNDS` | `12` | Tool round limit. |
| `OPENAI_API_KEY` | *(secret)* | Optional; `ask_cloud_llm` + fallback. |
| `CLOUD_MODEL` | `gpt-4o-mini` | Cloud model name. |

See [`.env.example`](.env.example) for a short checklist.

### local-llm

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | If using a gated Hugging Face model. |

## Warehouse Operations API (app)

Base path **`/v1/...`** (OpenAPI at `/docs` when the service is exposed).

- `GET /health`: liveness  
- `GET /v1/operations/summary`: open events by severity, SKUs below reorder, pending shipments, next cutoffs  
- `GET /v1/events`: query params `severity`, `type`, `warehouse_id`, `status`, `query`  
- `GET /v1/inventory`: query params `warehouse_id`, `sku`, `below_reorder`, `query`  
- `GET /v1/warehouses/{warehouse_id}`: site detail, open events, shipments  
- `POST /v1/events/{event_id}/acknowledge`: optional JSON body `{"note":"..."}`  

Data is **in-memory** synthetic seed data for demonstration.

## Demo script

```bash
./scripts/demo.sh
```

Override hosts if needed:

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
5. **Deployment:** Same three images on **Avassa** edge nodes with GPU for vLLM.

## Troubleshooting

- **Agent not ready:** Wait for vLLM model load.  
- **GPU:** Confirm **local-llm** has a GPU on the platform.  
- **Weak tool use:** Use a larger model and match `LOCAL_MODEL` to vLLM.
