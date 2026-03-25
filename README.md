# Edge agent demo

Tre containerbaserade tjänster som visar hur en **lokal LLM** (via vLLM) kan orkestrera anrop mot en **applikations-API** med verktyg, och valfritt eskalera till **moln-LLM** när modellen väljer verktyget `ask_cloud_llm`.

| Tjänst | Beskrivning | Standardport |
|--------|-------------|--------------|
| **app** | Mockad affärslogik: ärenden, sökning, åtgärder | 8001 |
| **agent** | Chat-API, verktygsloop, anropar app + lokal/moln-modell | 8002 |
| **local-llm** | vLLM med OpenAI-kompatibelt API | 8000 |

Flöde: användaren skickar ett meddelande till agenten → den lokala modellen kan anropa verktyg (`get_app_status`, `search_records`, `trigger_action`, `ask_cloud_llm`) → agenten kör verktygen (HTTP mot appen eller OpenAI för moln) → svar returneras. Web-UI finns på agentens rot-URL.

## Krav

- **Docker** med Compose (v2: `docker compose`).
- **NVIDIA GPU** + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html) för `local-llm` (vLLM).
- Tillräckligt **RAM/VRAM**; första starten laddar modellen från Hugging Face (kan ta flera minuter).

Valfritt: `curl` och `jq` om du kör demo-skriptet nedan med formaterad JSON.

## Snabbstart (lokal utveckling)

I projektroten:

```bash
docker compose up --build
```

När alla tjänster är friska:

- **UI:** [http://localhost:8002/](http://localhost:8002/)
- **App API:** [http://localhost:8001/docs](http://localhost:8001/docs)
- **Agent:** `POST http://localhost:8002/chat` med JSON `{"message":"..."}`

Stoppa med `Ctrl+C` eller `docker compose down`.

## Körning med images från GHCR (t.ex. Avassa / edge)

Efter att en version byggts i GitHub Actions (tag `v*`), sätt registry och samma versions-tagg för alla tre images:

```bash
export REGISTRY=ghcr.io/jbevemyr/edge-agent-demo
export VERSION=v0.1.0
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

Vid **privata** paket på GHCR: logga in på noden med `docker login ghcr.io` (PAT med `read:packages`) innan `pull`.

## Miljövariabler

### Filen `.env` (projektrot, läses av Compose)

| Variabel | Krävs? | Beskrivning |
|----------|--------|-------------|
| `OPENAI_API_KEY` | Nej | Om satt kan agenten anropa moln-LLM via verktyget `ask_cloud_llm` och vid fel på lokal modell som fallback. |
| `CLOUD_MODEL` | Nej | Modellnamn hos OpenAI (standard: `gpt-4o-mini`). |

Kopiera mallen och redigera:

```bash
cp .env.example .env
```

### Endast i `docker-compose.release.yml`

| Variabel | Krävs? | Beskrivning |
|----------|--------|-------------|
| `REGISTRY` | Ja | Bas-URL till containerregistry, t.ex. `ghcr.io/jbevemyr/edge-agent-demo`. |
| `VERSION` | Ja | Samma tag som byggts i CI, t.ex. `v0.1.0`. |

`OPENAI_API_KEY` och `CLOUD_MODEL` kan även sättas i samma miljö eller i `.env` när du kör release-compose.

### Agentcontainern (sätts i Compose, sällan manuellt)

| Variabel | Standard | Beskrivning |
|----------|----------|-------------|
| `APP_URL` | `http://app:8001` | Bas-URL till app-tjänsten. |
| `LOCAL_LLM_BASE` | `http://local-llm:8000/v1` | OpenAI-kompatibel bas-URL till vLLM. |
| `LOCAL_MODEL` | `Qwen/Qwen2.5-0.5B-Instruct` | Modell-id som skickas till vLLM (ska matcha modellen som vLLM startats med). |
| `LOCAL_LLM_API_KEY` | `local` | Dummy-nyckel till OpenAI-klienten mot vLLM (vLLM kräver ofta valfri sträng). |
| `MAX_TOOL_ROUNDS` | `12` | Max antal verktygsvarv i en chattur. |

### vLLM / Hugging Face

| Variabel | Beskrivning |
|----------|-------------|
| `HF_TOKEN` / `HUGGING_FACE_HUB_TOKEN` | Behövs bara om du byter till en **gated** modell; lägg då till `environment` på `local-llm` i compose. |

Modell och vLLM-flaggor styrs i compose-filens `command` under `local-llm` (standard: `Qwen/Qwen2.5-0.5B-Instruct`).

## Vad appen exponerar (exempel)

- `GET /health` — enkel hälsa  
- `GET /status` — antal ärenden, hur många som är `overdue`, senaste åtgärder  
- `GET /search?query=&status=` — sök/filter på mockade kundärenden  
- `POST /action` — JSON `{"action_id":"..."}` för demoåtgärder  

Datat är in-memory mock för demo.

## CI/CD (GitHub Actions)

Vid push av en git-tagg som matchar `v*` byggs och pushas tre images till **GHCR** med **samma tag**:

- `ghcr.io/<owner>/<repo>/app:<tag>`
- `ghcr.io/<owner>/<repo>/agent:<tag>`
- `ghcr.io/<owner>/<repo>/local-llm:<tag>` (tunn image ovanpå `vllm/vllm-openai`)

Manuell körning med valfri tagg finns under **Actions → Run workflow**.

## Demoskript

Skriptet anropar hälsa-endpoints, appens status och två exempel-frågor till agenten:

```bash
chmod +x scripts/demo.sh
./scripts/demo.sh
```

Anpassa bas-URL:er om du inte kör lokalt:

```bash
APP_URL=http://192.168.1.10:8001 \
LLM_URL=http://192.168.1.10:8000 \
AGENT_URL=http://192.168.1.10:8002 \
./scripts/demo.sh
```

Utan `jq` skrivs rå JSON från `curl`.

## Förslag på muntlig demo (kort)

1. Visa arkitektur: app / agent / lokal LLM (+ moln vid behov).  
2. `docker compose up` eller öppna UI på port 8002.  
3. Fråga: *”Hur många ärenden är försenade?”* — peka på verktygsanrop i svarets `audit` (JSON) om du använder API.  
4. Fråga om en **längre sammanfattning** eller uttryckligen be om moln — om `OPENAI_API_KEY` är satt kan modellen anropa `ask_cloud_llm`.  
5. Visa `GET /status` eller OpenAPI på appen (port 8001) för att koppla till ”system under test”.

## Felsökning

- **Agent startar inte:** vänta tills `local-llm` är klar (healthcheck kan ta många minuter första gången).  
- **GPU:** kontrollera `nvidia-smi` på värden och att containrar startas med GPU-stöd (`gpus: all` i compose).  
- **Tomt eller dåligt svar från liten modell:** byt till större modell i `local-llm.command` och uppdatera `LOCAL_MODEL` på agenten så de matchar.
