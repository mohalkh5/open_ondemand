# LLM chatbot (Chainlit) for CURC / Open OnDemand

This repository packages a Chainlit chat UI that talks to **Ollama**, persists chat history in **SQLite** (via a Chainlit data layer), and is meant to run on **CU Research Computing** resources behind **Open OnDemand**.

## How it is launched on CURC

Open OnDemand stages the contents of `template/` (job scripts + `template/app/`) into each session's output directory. The job script runs Chainlit from the first available location:

1. `/curc/sw/uv_env/llm-chatbot-env/app/` (shared install, preferred when populated)
2. `app/` next to the job scripts (OOD-staged copy)

To avoid relying on the per-session staged copy, populate the shared path when releasing:

```bash
rsync -a template/app/ /curc/sw/uv_env/llm-chatbot-env/app/
```

Chat history is stored under `/projects/${USER}/.chainlit_data`.

## Project layout

```text
requirements.txt              # Python dependencies (install in the shared venv on CURC)
template/
  script.sh.erb               # OOD job: modules, env, chainlit run
  before.sh.erb               # OOD hook
  after.sh                    # OOD hook
  app/                        # Chainlit application (staged by OOD; also rsync to /curc/sw/ on release)
form.yml.erb                  # OOD job form
submit.yml.erb                # Slurm submission template
```

## Local or manual run

From `template/app`:

```bash
cd template/app
python -m pip install -r ../../requirements.txt
chainlit run app.py
```
