# LLM chatbot (Chainlit) for CURC / Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

## How it is launched on CURC

The OOD batch template runs the app from the `bin` directory:

```bash
cd bin
chainlit run --root-path /node/${host}/${port} --port $port --debug --host $(hostname -I) app.py
```

That path is defined in `template/script.sh.erb`.

## Voice input and spoken replies (free, no API keys)

Voice works like the [Chainlit Whisper cookbook](https://github.com/Chainlit/cookbook/blob/main/openai-whisper/app.py), but **without paid APIs**:

| Step | Technology | Cost |
|------|------------|------|
| Speech → text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) on the job GPU | Free |
| Text → speech | [edge-tts](https://github.com/rany2/edge-tts) (Microsoft Edge voices) | Free |

Hold **P** while speaking, release to send. The assistant reply is read aloud automatically.

**First session only:** faster-whisper downloads a model into `HF_HOME` (default `/projects/$USER/.cache/huggingface`). The job has a GPU (`gres=gpu:1`), so transcription runs locally.

**TTS note:** edge-tts needs outbound HTTPS from the compute node (no API key). If your node has no internet, you still get the text reply; set `CURC_VOICE_TTS=none` to skip spoken output.

Optional tuning via `~/.curc_chat_env` (copy from `template/curc_chat_env.example`):

```bash
export CURC_WHISPER_MODEL_SIZE="base"    # tiny | base | small
export CURC_TTS_VOICE="en-US-AriaNeural"
export CURC_VOICE_TTS="edge"             # or "none"
```

## Project layout

```text
requirements.txt              # Python dependencies (install in your venv on CURC)
template/
  script.sh.erb               # OOD job: modules, env, then `cd bin` + `chainlit run app.py`
  curc_chat_env.example       # Optional voice tuning (model size, TTS voice)
  before.sh.erb               # OOD hook (port discovery, etc.)
  after.sh.erb                # OOD hook (wait for port)
  bin/
    app.py                    # Thin entrypoint: logging + re-exports Chainlit callbacks
    system_prompt.txt         # System prompt for the model
    chainlit.md               # Default welcome copy (Chainlit UI)
    chainlit_en-US.md         # English (US) welcome copy
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

## Documentation

CU Research Computing documentation hub: [Navigating CURC Documentation](https://curc.readthedocs.io/en/latest/getting_started/navigating_docs.html).
