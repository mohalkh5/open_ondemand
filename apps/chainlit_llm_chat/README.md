# LLM chatbot (Chainlit) for CURC / Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

## How it is launched on CURC

Open OnDemand stages only the small job scripts under `template/` into each user's batch connect output directory.

Each job activates the shared Python env, loads Ollama, and runs Chainlit 

```bash
rsync -a app/ /curc/sw/uv_env/llm-chatbot-env/app/
```

For local development, override the path:

```bash
export CHAINLIT_APP_DIR=/path/to/checkout/app
```

Chat history is stored under `/projects/${USER}/.chainlit_data`.

## Project layout

```text
requirements.txt              # Python dependencies (install in the shared venv on CURC)
app/                          # Chainlit application (deploy into llm-chatbot-env/app on CURC)
  app.py                      # Thin entrypoint: logging + re-exports Chainlit callbacks
  system_prompt.txt           # System prompt for the model
  chainlit_en-US.md           # Chainlit welcome/readme copy (en-US)
  .chainlit/config.toml       # Chainlit UI / feature settings
  public/                     # Static assets (CSS, JS, logos)
  curc_chat/                  # Application logic
template/
  script.sh.erb               # OOD job: modules, env, chainlit run from shared path
  before.sh.erb               # OOD hook
  after.sh                    # OOD hook
form.yml.erb                  # OOD job form
submit.yml.erb                # Slurm submission template
```

## Local or manual run

From the `app` directory:

```bash
cd app
python -m pip install -r ../requirements.txt
chainlit run app.py
```