# LLM chatbot (Chainlit) for CURC / Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

User-facing documentation lives in [CURC LLM Chat Interface](https://curc.readthedocs.io/en/latest/open_ondemand/llm_chat_interface.html).

## How the OOD app launches

Open OnDemand stages the job scripts under `template/`. The Chainlit application source lives in `app/` at the repo root.

At job start, `template/script.sh.erb`:

1. Loads the shared Python venv at `/curc/sw/uv_env/llm-chatbot-env/`
2. Loads the `ollama` environment module (`ml ollama`) and optionally sets `OLLAMA_MODELS`
3. Sets `CHAINLIT_DATA_DIR` to `/projects/${USER}/.chainlit_data` where chat history is stored.
4. Runs `chainlit run app.py` from the resolved `app/` directory


## Repository layout

```
app/                          # Chainlit application
requirements.txt              # Python dependencies for the shared venv at /curc/sw/uv_env/llm-chatbot-env/
template/
  script.sh.erb               # OOD job: modules, env, chainlit run
  before.sh.erb               # OOD hook (port discovery)
  after.sh                    # OOD hook
form.yml.erb                  # OOD job form (model path, Slurm options)
submit.yml.erb                # Slurm submission template
manifest.yml                  # OOD app metadata
view.html.erb                 # OOD connect button
```

---

## Chainlit application (`app/`)

The Python application is a standard [Chainlit](https://docs.chainlit.io) project. `app.py` is the entry point; it imports handlers and registers side-effect modules (action callbacks, conversation starters).

### Architecture

```
User browser
    |
    v
Chainlit UI (config in app/.chainlit/config.toml, custom CSS/JS in app/public/)
    |
    v
app/app.py  -->  curc_chat/chainlit_handlers.py  (@cl.on_message, @cl.on_chat_start, ...)
    |                    |
    |                    +--> Ollama AsyncClient (localhost:11434)
    |                    |
    |                    +--> curc_chat/hpc_files.py  (/file path attachments)
    |                    |
    |                    +--> curc_chat/storage/sqlite_layer.py  (per-user chat history)
    v
Ollama server (started by `ml ollama` in script.sh.erb on the compute node)
```

### Module reference

| Path | Purpose |
|------|---------|
| `app/app.py` | Entry point: imports handlers, action callbacks, and starters |
| `app/chainlit_en-US.md` | User-facing readme shown in the Chainlit UI |
| `app/system_prompt.txt` | Default system prompt sent to Ollama on each turn |
| `app/.chainlit/config.toml` | Chainlit UI settings (theme, file upload, custom CSS/JS) |
| `app/public/custom.css` | styling (link colors, hide attach/feedback controls) |
| `app/public/custom.js` | Welcome page, CURC logo |
| `curc_chat/chainlit_handlers.py` | Main chat logic: profiles, message handling, Ollama streaming |
| `curc_chat/models/ollama_models.py` | List models from Ollama; cache and error messages |
| `curc_chat/hpc_files.py` | Parse `/file` paths; validate CURC filesystem roots |
| `curc_chat/uploads.py` | Read attached files (text, code, PDF, images) for the prompt |
| `curc_chat/storage/sqlite_layer.py` | Per-user SQLite data layer for threads and messages |
| `curc_chat/auth.py` | Header-based auth token for Chainlit sessions |
| `curc_chat/message_actions.py` | Build Regenerate / New chat / Copy code action buttons |
| `curc_chat/action_handlers.py` | Callbacks for message action buttons |
| `curc_chat/starters.py` | Welcome-screen conversation starter prompts |
| `curc_chat/settings.py` | Environment variable helpers (context size, attach limits, etc.) |

### Request flow (one user message)

1. **`@cl.on_message`** (`chainlit_handlers.py`) receives the user text.
2. **`process_hpc_attachments`** (`hpc_files.py`) looks for `/file /path/to/file` commands or bare absolute paths. Paths must be under allowed CURC roots (`/home/$USER`, `/projects/$USER`, `/scratch/alpine/$USER`, `/pl/active`). If any attachment fails, the turn stops and nothing is sent to the model.
3. **`handle_user_turn`** builds the Ollama message list (system prompt + slim history + full content for the latest user turn only).
4. **`client.chat`** streams the response from the selected Ollama model.
5. Assistant actions (**Regenerate**, **New chat**, **Copy code block**, optional **Switch to vision model**) are attached to the reply.
6. History is persisted via the SQLite data layer under `CHAINLIT_DATA_DIR`.

### Models

- **Discovery:** `@cl.set_chat_profiles` calls Ollama's list API and exposes each completion-capable model as a chat profile.
- **Selection:** Users pick a model from the header dropdown when multiple models exist. When only one model is available, Chainlit hides the dropdown; the app shows the active model in Chat Settings and on the welcome screen.
- **OOD form:** `form.yml.erb` field `model_path` controls where Ollama looks for models. Default `CURC LLM Models` uses the module default; a custom path sets `OLLAMA_MODELS` before `ml ollama` in `script.sh.erb`.

### File attachments

Browser upload is **disabled** in `config.toml`. Users attach files from Alpine storage by including paths in their message:

```
/file /projects/$USER/myfile.pdf
```

or a single absolute path on its own line. Supported types include text, code, PDF (text extraction), and images (for vision-capable models).

### Chat history

- Stored per user under `/projects/${USER}/.chainlit_data` (set in `script.sh.erb`).
- Implemented in `curc_chat/storage/sqlite_layer.py` as Chainlit's `BaseDataLayer`.
- Resume reloads slim message history (large PDF bodies are not re-injected on resume).

### UI customization

- **Feedback buttons** (thumbs up/down) are disabled via `disable_human_feedback=True` on all messages (`curc_message()` helper). CSS/JS in `public/` is a fallback.
- **Attach button** is hidden in CSS/JS because attachments use HPC paths only.
- **Welcome disclaimer** is injected by `public/custom.js` on the empty-state screen.

### Environment variables

Set in `script.sh.erb` or optionally overridden per user (not documented for end users unless needed):

| Variable | Set by | Purpose |
|----------|--------|---------|
| `CHAINLIT_DATA_DIR` | `script.sh.erb` | SQLite chat history location |
| `OLLAMA_MODELS` | `script.sh.erb` (custom model path) | Ollama model directory |
| `OLLAMA_HOST` | optional | Ollama API host (default `localhost:11434`) |
| `CURC_OLLAMA_NUM_CTX` | optional | Ollama context window (default `32768`) |
| `CURC_OLLAMA_NUM_PREDICT` | optional | Max tokens to generate (default `4096`) |
| `CURC_CHAT_MAX_ATTACH_MB` | optional | Per-file attach limit (default `500`) |
| `CURC_CHAT_MAX_ATTACH_FILES` | optional | Max files per message (default `20`) |
| `CURC_CHAT_MAX_PDF_CHARS` | optional | Max PDF text chars per file (default `120000`) |

### Dependencies

Installed into `/curc/sw/uv_env/llm-chatbot-env/` from `requirements.txt`:

- `chainlit` — web UI framework
- `ollama` — Python client for the Ollama HTTP API
- `aiosqlite` — async SQLite for the data layer
- `Pillow`, `PyPDF2` — image and PDF handling for attachments

---

## Local development

From the repo:

```bash
cd apps/chainlit_llm_chat/app
python -m pip install -r ../requirements.txt

# Ollama must be running locally with at least one model pulled
export CHAINLIT_DATA_DIR="${HOME}/.chainlit_data"
chainlit run app.py
```
