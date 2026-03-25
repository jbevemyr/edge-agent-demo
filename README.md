# Edge agent demo

Three containers that show how a **local LLM** (vLLM) can orchestrate **tool calls** against an **application HTTP API**, and optionally escalate to a **cloud LLM** when the model invokes the `ask_cloud_llm` tool.

| Service | Role | Default port |
|---------|------|--------------|
| **app** | Mock business API: cases, search, actions | 8001 |
| **agent** | Chat API, tool loop, calls app + local/cloud models | 8002 |
| **local-llm** | vLLM with an OpenAI-compatible HTTP API | 8000 |

**Flow:** the user sends a message to the agent → the local model may call tools (`get_app_status`, `search_records`, `trigger_action`, `ask_cloud_llm`) → the agent executes them (HTTP to the app or OpenAI for cloud) → the final reply is returned. A small web UI is served at the agent root URL.

## Requirements

- **Container images** from **GHCR**, built by this repo’s CI (three images, one shared version tag).
- **NVIDIA GPU** on hosts running **local-llm**, as configured in your edge platform (on Avassa: [GPU passthrough](https://docs.avassa.io/how-to/applications#request-gpu-passthrough)).
- Enough **RAM/VRAM**; the first start downloads the model from Hugging Face (can take many minutes).

Optional: `curl` and `jq` for formatted JSON from `scripts/demo.sh` (against whatever hostnames/ingress you expose).

## Run on Avassa

The intended way to run this demo is an **Avassa application specification** plus an **application deployment**.

1. **Application spec** — services, images, `env`, volumes, ingress, outbound, GPU, secrets. Official reference: **[Applications | Avassa Docs](https://docs.avassa.io/how-to/applications)**. Start from [`avassa/application.example.yaml`](avassa/application.example.yaml) and adjust registry paths, version tag, internal hostnames, GPU labels, and networking for your tenant and site.

2. **Deployment** — which edge sites get the app and how rollouts run. See **[Application Deployment | Avassa Docs](https://docs.avassa.io/how-to/deploying-applications)** and [`avassa/deployment.example.yaml`](avassa/deployment.example.yaml).

**Mapping this demo to Avassa:**

| Concern | Notes |
|--------|--------|
| **Images** | Use the three GHCR images from CI with the **same** tag (e.g. `…/app:v0.1.0`, `…/agent:v0.1.0`, `…/local-llm:v0.1.0`). |
| **Environment** | Set container `env` ([add environment variables](https://docs.avassa.io/how-to/applications#add-environment-variables-to-a-container)). Agent needs at least `APP_URL`, `LOCAL_LLM_BASE`, `LOCAL_MODEL`; optionally `OPENAI_API_KEY` / `CLOUD_MODEL`. |
| **Internal URLs** | Point `APP_URL` and `LOCAL_LLM_BASE` at the **app** and **local-llm** services on the application private network ([Configuring application networks](https://docs.avassa.io/how-to/applications-and-deployments/configuring-application-networks)). |
| **GPU** | Request GPU for **local-llm** ([GPU passthrough](https://docs.avassa.io/how-to/applications#request-gpu-passthrough)). |
| **Model cache** | Mount an [ephemeral](https://docs.avassa.io/how-to/applications#add-ephemeral-volume-configuration-to-a-service) or [persistent](https://docs.avassa.io/how-to/applications#add-persistent-volume-configuration-to-a-service) volume on vLLM’s Hugging Face cache path (e.g. `/root/.cache/huggingface`), as in `application.example.yaml`. |
| **Ingress** | Expose TCP **8002** on the agent service for the UI ([ingress](https://docs.avassa.io/how-to/applications#add-ingress-ip-configuration-to-a-service)); optionally 8001 for app docs. |
| **Outbound** | If using `OPENAI_API_KEY`, allow HTTPS to OpenAI ([outbound access](https://docs.avassa.io/how-to/applications#allow-unrestricted-outbound-network-access-for-a-service) or tighter rules). |
| **Secrets** | Prefer [Strongbox](https://docs.avassa.io/how-to/applications#add-strongbox-secrets-to-an-application) instead of inline API keys. |

### Deploying to edge sites

| Topic | What to use |
|--------|-------------|
| **Placement** | [Site labels](https://docs.avassa.io/how-to/deploying-applications#placing-applications-based-on-labels) — e.g. `system/name` for one site, `system/type = edge` for all edge sites (case-sensitive). |
| **Rolling deploy** | [`deploy-to-sites`](https://docs.avassa.io/how-to/deploying-applications#rolling-deployments) with `sites-in-parallel` and `healthy-time`; `supctl show application-deployments <name>`. |
| **Canary** | [`canary-sites`](https://docs.avassa.io/how-to/deploying-applications#canary-deployments) + `canary-healthy-time`. |
| **New sites** | [`supctl do application-deployments <name> redeploy`](https://docs.avassa.io/how-to/deploying-applications#adding-sites-to-a-deployment). |

## Container images (CI → GHCR)

Pushing a git tag matching `v*` builds and pushes:

- `ghcr.io/<owner>/<repo>/app:<tag>`
- `ghcr.io/<owner>/<repo>/agent:<tag>`
- `ghcr.io/<owner>/<repo>/local-llm:<tag>` (thin wrapper on `vllm/vllm-openai`)

Manual builds: **Actions → Build and push container images → Run workflow**.

If packages are **private**, ensure your edge environment can authenticate to GHCR (`docker login` / registry credentials as required by Avassa).

## Environment variables

Set these on the relevant **containers** in the Avassa application spec (or via variables / vault → `env`).

### Agent service

| Variable | Typical value | Description |
|----------|---------------|-------------|
| `APP_URL` | `http://app:8001` | Base URL of the app service (hostname must resolve on the app network). |
| `LOCAL_LLM_BASE` | `http://local-llm:8000/v1` | OpenAI-compatible base URL for vLLM. |
| `LOCAL_MODEL` | `Qwen/Qwen2.5-0.5B-Instruct` | Model id for API calls to vLLM (must match vLLM startup). |
| `LOCAL_LLM_API_KEY` | `local` | Placeholder API key for the OpenAI client to vLLM. |
| `MAX_TOOL_ROUNDS` | `12` | Maximum tool rounds per chat request. |
| `OPENAI_API_KEY` | *(secret)* | Optional; enables `ask_cloud_llm` and cloud fallback on local errors. |
| `CLOUD_MODEL` | `gpt-4o-mini` | OpenAI model name when using the cloud path. |

See [`.env.example`](.env.example) for a short optional-variable checklist.

### local-llm service

| Variable | Description |
|----------|-------------|
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | Only if you use a **gated** Hugging Face model. |

Model and engine flags are set with `cmd` / entrypoint on the **local-llm** container (see `application.example.yaml`).

## App API (examples)

- `GET /health` — liveness  
- `GET /status` — case counts, `overdue` count, recent actions  
- `GET /search?query=&status=` — search/filter mock customer cases  
- `POST /action` — JSON `{"action_id":"..."}` for demo actions  

Data is in-memory mock data for demonstration only.

## Demo script

After the app is reachable (e.g. via ingress or port-forward, depending on your setup):

```bash
./scripts/demo.sh
```

Point at your exposed endpoints:

```bash
APP_URL=http://<app-host>:8001 \
LLM_URL=http://<llm-host>:8000 \
AGENT_URL=http://<agent-host>:8002 \
./scripts/demo.sh
```

Without `jq`, responses are raw JSON from `curl`.

## Suggested talking points for a live demo

1. Show the split: **app** / **agent** / **local-llm** (+ optional cloud).  
2. Open the agent UI on **8002** (or your ingress URL).  
3. Ask: *“How many cases are overdue?”* — highlight tool usage in the JSON `audit` field when using the API.  
4. Ask for a **longer summary** or cloud help — with `OPENAI_API_KEY` set, the model may call `ask_cloud_llm`.  
5. Show `GET /status` or app OpenAPI on **8001** if exposed.

## Troubleshooting

- **Agent not ready:** wait until **local-llm** has finished pulling/loading the model.  
- **GPU:** confirm the **local-llm** service has a GPU assigned per your platform (Avassa `gpu:` block and site capabilities).  
- **Weak answers:** use a larger model in vLLM `cmd` and set `LOCAL_MODEL` on the agent to match.
