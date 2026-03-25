# Edge agent demo

Three containers that show how a **local LLM** (vLLM) can orchestrate **tool calls** against an **application HTTP API**, and optionally escalate to a **cloud LLM** when the model invokes the `ask_cloud_llm` tool.

| Service | Role | Default port |
|---------|------|--------------|
| **app** | Mock business API: cases, search, actions | 8001 |
| **agent** | Chat API, tool loop, calls app + local/cloud models | 8002 |
| **local-llm** | vLLM with an OpenAI-compatible HTTP API | 8000 |

**Flow:** the user sends a message to the agent → the local model may call tools (`get_app_status`, `search_records`, `trigger_action`, `ask_cloud_llm`) → the agent executes them (HTTP to the app or OpenAI for cloud) → the final reply is returned. A small web UI is served at the agent root URL.

## Requirements

- **Docker** with Compose v2 (`docker compose`).
- **NVIDIA GPU** on the host running **local-llm**, plus the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) (vLLM).
- Enough **RAM/VRAM**; the first start downloads the model from Hugging Face (can take many minutes).

Optional: `curl` and `jq` for formatted JSON from `scripts/demo.sh`.

## Quick start (local development)

From the repository root:

```bash
docker compose up --build
```

When services are healthy:

- **UI:** [http://localhost:8002/](http://localhost:8002/)
- **App API docs:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Agent:** `POST http://localhost:8002/chat` with JSON `{"message":"..."}`

Stop with `Ctrl+C` or `docker compose down`.

## Pre-built images from GHCR

After CI has built a `v*` tag, set the registry and the **same** image tag for all three images:

```bash
export REGISTRY=ghcr.io/jbevemyr/edge-agent-demo
export VERSION=v0.1.0
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

For **private** GHCR packages, run `docker login ghcr.io` on the host (PAT with `read:packages`) before `pull`.

## Running on Avassa

Avassa applications are described in YAML: services, container images, `env`, volumes, networking (ingress / outbound), GPU passthrough, and secrets. See the official guide: **[Applications | Avassa Docs](https://docs.avassa.io/how-to/applications)**.

**Mapping this demo to Avassa:**

| Concern | Notes |
|--------|--------|
| **Images** | Use the three GHCR images built by CI, all with the **same** tag (e.g. `…/app:v0.1.0`, `…/agent:v0.1.0`, `…/local-llm:v0.1.0`). |
| **Environment** | Set container `env` as in the docs ([add environment variables](https://docs.avassa.io/how-to/applications#add-environment-variables-to-a-container)). Agent needs at least `APP_URL`, `LOCAL_LLM_BASE`, `LOCAL_MODEL`; optionally `OPENAI_API_KEY` / `CLOUD_MODEL` for cloud escalation. |
| **Internal URLs** | Point `APP_URL` and `LOCAL_LLM_BASE` at the **app** and **local-llm** services on the application private network (hostname/DNS depends on your site; see [Configuring application networks](https://docs.avassa.io/how-to/applications-and-deployments/configuring-application-networks) in the Avassa docs). |
| **GPU** | Request GPU for the **local-llm** container per [GPU passthrough](https://docs.avassa.io/how-to/applications#request-gpu-passthrough) (and the GPU passthrough tutorial linked there). |
| **Model cache** | Add an [ephemeral](https://docs.avassa.io/how-to/applications#add-ephemeral-volume-configuration-to-a-service) or [persistent](https://docs.avassa.io/how-to/applications#add-persistent-volume-configuration-to-a-service) volume and mount it where vLLM stores the Hugging Face cache (e.g. `/root/.cache/huggingface`), similar to the Compose volume in this repo. |
| **Ingress** | Expose TCP **8002** on the agent service if users should open the UI from the site network ([ingress IP configuration](https://docs.avassa.io/how-to/applications#add-ingress-ip-configuration-to-a-service)). |
| **Outbound** | If you use `OPENAI_API_KEY`, allow outbound HTTPS to OpenAI’s API ([outbound access](https://docs.avassa.io/how-to/applications#allow-unrestricted-outbound-network-access-for-a-service) or restricted rules). |
| **Secrets** | Prefer [Strongbox](https://docs.avassa.io/how-to/applications#add-strongbox-secrets-to-an-application) or vault-backed variables instead of plain-text API keys in specs. |

An **illustrative** (non-validated) skeleton lives in [`avassa/application.example.yaml`](avassa/application.example.yaml). Replace registry paths, version, hostnames, GPU labels, and network rules to match your tenant and site.

## Environment variables

### `.env` in the repo root (used by Compose)

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | No | If set, the agent can call the cloud via `ask_cloud_llm` and use cloud fallback when the local model errors. |
| `CLOUD_MODEL` | No | OpenAI model name (default: `gpt-4o-mini`). |

Copy and edit:

```bash
cp .env.example .env
```

### `docker-compose.release.yml` only

| Variable | Required | Description |
|----------|----------|-------------|
| `REGISTRY` | Yes | Registry base, e.g. `ghcr.io/jbevemyr/edge-agent-demo`. |
| `VERSION` | Yes | Same tag as built in CI, e.g. `v0.1.0`. |

You can also pass `OPENAI_API_KEY` and `CLOUD_MODEL` via the shell or `.env` when using the release compose file.

### Agent container (normally set in Compose / Avassa `env`)

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_URL` | `http://app:8001` | Base URL of the app service. |
| `LOCAL_LLM_BASE` | `http://local-llm:8000/v1` | OpenAI-compatible base URL for vLLM. |
| `LOCAL_MODEL` | `Qwen/Qwen2.5-0.5B-Instruct` | Model id sent to vLLM (must match how vLLM was started). |
| `LOCAL_LLM_API_KEY` | `local` | Placeholder API key for the OpenAI client talking to vLLM. |
| `MAX_TOOL_ROUNDS` | `12` | Maximum tool rounds per chat request. |

### vLLM / Hugging Face

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | Only if you switch to a **gated** model; add to the local-llm container environment in Compose or Avassa. |

Model and vLLM flags are set in the `local-llm` `command` / `cmd` in Compose or Avassa (default model: `Qwen/Qwen2.5-0.5B-Instruct`).

## App API (examples)

- `GET /health` — liveness  
- `GET /status` — case counts, `overdue` count, recent actions  
- `GET /search?query=&status=` — search/filter mock customer cases  
- `POST /action` — JSON `{"action_id":"..."}` for demo actions  

Data is in-memory mock data for demonstration only.

## CI/CD (GitHub Actions)

Pushing a git tag matching `v*` builds and pushes three images to **GHCR** with the **same** tag:

- `ghcr.io/<owner>/<repo>/app:<tag>`
- `ghcr.io/<owner>/<repo>/agent:<tag>`
- `ghcr.io/<owner>/<repo>/local-llm:<tag>` (thin image on top of `vllm/vllm-openai`)

Manual runs: **Actions → Build and push container images → Run workflow**.

## Demo script

The script hits health endpoints, app status, and sends two sample chat requests to the agent:

```bash
./scripts/demo.sh
```

Override base URLs if not on localhost:

```bash
APP_URL=http://192.168.1.10:8001 \
LLM_URL=http://192.168.1.10:8000 \
AGENT_URL=http://192.168.1.10:8002 \
./scripts/demo.sh
```

Without `jq`, responses are raw JSON from `curl`.

## Suggested talking points for a live demo

1. Show the split: **app** (system under test) / **agent** (orchestration) / **local-llm** (inference), plus optional cloud.  
2. Run `docker compose up` or open the UI on port 8002.  
3. Ask: *“How many cases are overdue?”* — highlight tool usage in the JSON `audit` field when using the API.  
4. Ask for a **longer summary** or explicitly request cloud help — with `OPENAI_API_KEY` set, the model may call `ask_cloud_llm`.  
5. Show `GET /status` or the app OpenAPI on port 8001.

## Troubleshooting

- **Agent does not start:** wait until **local-llm** is ready (first pull/model load can take a long time).  
- **GPU:** check `nvidia-smi` on the host and that the runtime passes a GPU into the vLLM container (`gpus: all` in Compose; GPU block on Avassa).  
- **Weak answers from a tiny model:** use a larger model in the local-llm command and set `LOCAL_MODEL` on the agent to match.
