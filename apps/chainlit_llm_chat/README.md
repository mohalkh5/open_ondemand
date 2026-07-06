# LLM chatbot (Chainlit) for CURC Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

User-facing documentation lives in [CURC LLM Chat Interface](https://curc.readthedocs.io/en/latest/open_ondemand/llm_chat_interface.html).

## How the OOD app launches

Open OnDemand stages the job scripts under `template/`. The Chainlit application source lives in `app/` at the repository root.

When a user launches an LLM Chat Interface session, template/script.sh.erb performs the following steps:

1. Activates the shared Python virtual environment located at `/curc/sw/uv_env/llm-chatbot-env/`
2. Loads the `Ollama` environment module (`ml ollama`) and sets the `OLLAMA_MODELS` environment variable to default path.
3. Sets `CHAINLIT_DATA_DIR=/projects/${USER}/.chainlit_data` which stores the user's SQLite chat history.
4. Starts the Chainlit application, `chainlit run app.py`


## Application Architecture

The Python application follows a standard Chainlit project structure. `app.py` serves as the application entry point and imports the message handlers, conversation starters, and action callbacks.

```
Browser
   │
   ▼
Chainlit UI (config in app/.chainlit/config.toml, custom CSS/JS in app/public/)
   │
   ▼
app.py
   │
   ├── Message handlers
   ├── Attachment processing
   ├── SQLite history
   └── Ollama client
           │
           ▼
      Ollama Server
```

### Repository Layout
```
├── app/                              # Chainlit application source
│   ├── app.py                        # Application entry point; registers handlers and starts the chat app
│   ├── chainlit_en-US.md             # Help/documentation displayed inside the Chainlit interface
│   ├── system_prompt.txt             # Default system prompt prepended to every conversation
│   ├── .chainlit/
│   │   └── config.toml               # Chainlit configuration (theme, UI options, uploads, etc.)
│   ├── public/
│   │   ├── custom.css                # Custom styling for the chat interface
│   │   └── custom.js                 # Frontend customizations (welcome page, branding, UI behavior)
│   └── curc_chat/                    # Core chatbot implementation
│       ├── action_handlers.py        # Callbacks for custom message action buttons
│       ├── auth.py                   # Header-based authentication for OOD sessions
│       ├── chainlit_handlers.py      # Main chat lifecycle and message processing logic
│       ├── hpc_files.py              # Processes and validates HPC filesystem path attachments
│       ├── message_actions.py        # Creates Regenerate, New Chat, Copy Code, and related actions
│       ├── settings.py               # Environment variable parsing and application settings
│       ├── starters.py               # Conversation starter prompts shown on the welcome screen
│       ├── uploads.py                # Reads and extracts content from supported file types
│       ├── models/
│       │   └── ollama_models.py      # Discovers available Ollama models and builds chat profiles
│       └── storage/
│           └── sqlite_layer.py       # SQLite-backed Chainlit data layer for chat history
│
├── template/                         # Open OnDemand job templates
│   ├── before.sh.erb                 # Pre-launch hook (port discovery)
│   ├── script.sh.erb                 # Main job launch script; loads environment and starts Chainlit
│   └── after.sh                      # Cleanup hook executed when the job exits
│
├── form.yml.erb                      # Open OnDemand job submission form (resources, model path, etc.)
├── submit.yml.erb                    # Slurm submission template used by Open OnDemand
├── manifest.yml                      # Open OnDemand application metadata
├── view.html.erb                     # Open OnDemand connection page ("Connect" button)
├── requirements.txt                  # Python dependencies for the shared virtual environment
└── README.md                         # Developer documentation for this repository
```

### Request flow

1. Chainlit receives the user message (`@cl.on_message`).
2. Any referenced HPC file paths are validated and processed.
3. The prompt is assembled from the system prompt, conversation history, and current message.
4. The request is streamed to Ollama.
5. Action buttons are added to the assistant response.
6. The conversation is persisted to SQLite.

### Models

- **Discovery:** `@cl.set_chat_profiles` calls Ollama's list API and exposes each completion-capable model as a chat profile.
- **Selection:** Users pick a model from the header dropdown when multiple models exist. When only one model is available, Chainlit hides the dropdown; the app shows the active model in Chat Settings and on the welcome screen.

### File attachments

Browser upload is **disabled** in `config.toml`. Users attach files from Alpine filesystems by including paths in their message:

```
/file /projects/$USER/myfile.pdf
```

Supported types include text, code, PDF (text extraction), and images (for vision-capable models).

### Chat history

- Stored per user under `/projects/${USER}/.chainlit_data` (set in `script.sh.erb`).
- Implemented in `curc_chat/storage/sqlite_layer.py` as Chainlit's `BaseDataLayer`.
- Resume reloads slim message history (large PDF bodies are not re-injected on resume).

### Environment variables

Set in `script.sh.erb`:

| Variable | Set by | Purpose |
|----------|--------|---------|
| `CHAINLIT_DATA_DIR` | `script.sh.erb` | SQLite chat history location |
| `OLLAMA_MODELS` | `script.sh.erb` (custom model path) | Ollama model directory |
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

## Running Locally

From the repository root:

```bash
cd apps/chainlit_llm_chat/app
python -m pip install -r ../requirements.txt

# Ollama must be running locally with at least one model pulled
export CHAINLIT_DATA_DIR="${HOME}/.chainlit_data"
chainlit run app.py
```
