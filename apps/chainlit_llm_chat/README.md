# LLM chatbot (Chainlit) for CURC / Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

## How it is launched on CURC

The OOD batch template runs the app from the `bin` directory:

```bash
cd bin
chainlit run --root-path /node/${host}/${port} --port $port --debug --host $(hostname -I) app.py
```

That path is defined in `template/script.sh.erb`.

## Project layout

```text
requirements.txt              # Python dependencies (install in your venv on CURC)
template/
  script.sh.erb               # OOD job: modules, env, then `cd bin` + `chainlit run app.py`
  before.sh.erb               # OOD hook
  after.sh.erb                # OOD hook
  bin/
    app.py                    # Thin entrypoint: logging + re-exports Chainlit callbacks
    system_prompt.txt         # System prompt for the model
    chainlit_en-US.md         # Chainlit welcome/readme copy (en-US)
    .chainlit/config.toml     # Chainlit UI / feature settings
    public/                   # Static assets (e.g. theme)
    curc_chat/                # Application logic (refactored package)
      __init__.py
      settings.py             # Paths / env (e.g. OLLAMA_HOST, system prompt path)
      security.py             # POSIX file permission helper
      uploads.py              # Attachments: text, PDF, images for the model
      auth.py                 # Header auth + per-user token file (~/.chainlit_auth_token)
      chainlit_handlers.py    # @cl.on_message, profiles, data layer wiring, Ollama streaming
      models/
        ollama_models.py      # Ollama model list + cache
      storage/
        sqlite_layer.py       # SQLite BaseDataLayer implementation
    auth.py
    data_layer.py
    models.py
    utils.py
```

## Local or manual run

From the `template/bin` directory:

```bash
cd template/bin
python -m pip install -r ../../requirements.txt
chainlit run app.py
```