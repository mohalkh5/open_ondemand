# LLM chatbot (Chainlit) for CURC / Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

## How it works

Open OnDemand stages only the job scripts under `template/` into each session's output directory (the same pattern as Jupyter, VS Code Server, and RStudio). The Chainlit application source lives in `app/` at the repo root and is **not** staged per session.

At job start, `template/script.sh.erb` activates the shared Python environment at `/curc/sw/uv_env/llm-chatbot-env/` and runs Chainlit from this app's `app/` directory. OOD writes that path into the job script at launch (it is not copied into the session output directory).

Chat history is stored under `/projects/${USER}/.chainlit_data`.

## Project layout

```text
app/                          # Chainlit application source (not staged by OOD)
requirements.txt              # Python dependencies for the shared venv
template/
  script.sh.erb               # OOD job: modules, env, chainlit run
  before.sh.erb               # OOD hook (port discovery)
  after.sh                    # OOD hook
form.yml.erb                  # OOD job form
submit.yml.erb                # Slurm submission template
```

## Local or manual run

From `app/`:

```bash
cd app
python -m pip install -r ../requirements.txt
chainlit run app.py
```
