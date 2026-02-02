# 3C3H Evaluation Pipeline

A fully–automated, **Apache‑2.0–licensed** toolkit that generates answers from language models (open‑weight *and* proprietary), judges them with LLM‑as‑a‑Judge following the **3C3H** (Correctness, Completeness, Conciseness, Helpfulness, Honesty, Harmlessness) evaluation score criterias which were first introduced [here](https://huggingface.co/blog/leaderboard-3c3h-aragen) and produces leaderboard‑ready scores to report.

> **Why?**
> Measuring the real‑world utility and safety of LLMs at scale requires a reproducible, end‑to‑end pipeline. This repository powers currently the [*Arabic Leaderboards*](https://huggingface.co/spaces/inceptionai/Arabic-Leaderboards) and related internal evaluations at **G42**'s **Inception**.

---

## ✨ Key Features

| Phase | Script | Highlights |
|-------|--------|------------|
| **Generation — Open Models** | `pipeline/generate-oma.py` | Local HF models (Text & Text + Vision), automatic multi‑GPU sharding, chat‐template detection. |
| **Generation — Proprietary Models** | `pipeline/generate-pma.py` | Unified wrapper over OpenAI, Anthropic, Google Gemini, DeepSeek, Mistral, xAI Grok, and Inception APIs with key auto‑discovery and rate‑limit handling. |
| **Judging** | `pipeline/jury.py` | Multi‑judge voting or averaging, Claude 3.5 & GPT‑4o support, per‑round prompts, zero‑score propagation, JSON extraction robustness. |
| **Aggregation** | `pipeline/averaging-to-results.py` | Merges *_judged.json* files, computes per‑judge and per‑task averages, writes batch‑scoped `results/*.json`. |
| **Orchestration** | `pipeline/run-pipeline.sh` | SLURM job: model sync → generation → judging → aggregation → (optional) HF Hub sync. |

---

## 🗂️ Repository Layout

```
├── tasks/                     # Input datasets (e.g. AraGen-12‑2024.json)
├── models/                    # Local cache of open‑weight models (Optional)
├── pipeline/
│   ├── generate-oma.py        # Open‑weight answer generation
│   ├── generate-pma.py        # Proprietary answer generation
│   ├── jury.py                # LLM‑as‑a‑Judge
│   ├── averaging-to-results.py
│   ├── run-pipeline.sh        # SLURM pipeline script
│   ├── requirements.txt       # requirements file to be installed
│   ├── utils/                 # Sync helpers (Hub ↔ local)
│   └── prompts/               # Different versions of the Judge System Prompts
├── requests/                  # Task-specific model requests
│   └── <task-name>/           # e.g. AraGen-12-2024-dev/
│       ├── OpenRequests/      # Open-source model requests
│       └── ProprietaryRequests/ # Proprietary model requests
├── answers/                   # Generated model answers
│   └── <task-name>/          # Task-specific answers
├── results/                   # Aggregated 3C3H metrics
│   └── <task-name>/          # Task-specific results
└── logs/                     # Pipeline execution logs
    └── <task-name>/          # Task-specific logs
        └── <job-id>/         # Job-specific logs
```

---

## ⚡ Quick Start

```bash
# 1. Clone
$ git clone https://github.com/inceptionai-abudhabi/3C3H.git
$ cd 3C3H

# 2. Create environment (Conda example)
$ conda create -n 3c3h python=3.10 -y
$ conda activate 3c3h
$ pip install -r ./pipeline/requirements.txt

# 3. Export **all** required API keys & HF token
$ export HF_TOKEN="<your-hf-token>"
$ export ANTHROPIC_API_KEY="..."
# ... OPENAI_API_KEY, GOOGLE_API_KEY, DEEPSEEK_API_KEY, MISTRAL_API_KEY, XAI_API_KEY

# 4. (Optional) Download models ahead‑of‑time
$ huggingface-cli download "inceptionai/jais-family-13b-chat" --local-dir models/inceptionai/jais-family-13b-chat

# 5. Launch the pipeline with desired options (Make sure to edit the SLURM header first):

# Process all pending requests with defaults:
$ sbatch ./pipeline/run-pipeline.sh

# Process specific model:
$ sbatch ./pipeline/run-pipeline.sh --model inceptionai/jais-family-13b-chat

# Process multiple models (mix of open and proprietary):
$ sbatch ./pipeline/run-pipeline.sh --model "inceptionai/jais-family-13b-chat,gpt-4o,claude-3-sonnet"

# Process with custom parameters:
$ sbatch ./pipeline/run-pipeline.sh --model inceptionai/jais-family-13b-chat \
  --task AraGen-12-2024 \
  --precision float16 \
  --params 13B \
  --env custom-env
```

## ⚙️ Configuration Reference

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--task` | Task name | AraGen-12-2024-dev |
| `--model` | Model name(s) - comma-separated for multiple | (all pending) |
| `--env` | Conda environment name | 3c3h |
| `--license` | License type | Open |
| `--revision` | Model revision | main |
| `--precision` | Model precision | bfloat16 |
| `--params` | Model parameters | 0 |
| `--status` | Model status | RUNNING |
| `--modality` | Model modality | Text (Accepted values: "Text" || "Text+Vision")|

### Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `HF_TOKEN` | **Yes** | Authenticate to Hugging Face for dataset & model pulls/pushes. |
| `OPENAI_API_KEY` | Yes (if using GPT‑4/4o) | OpenAI models. |
| `ANTHROPIC_API_KEY` | Yes (if using Claude) | Anthropic models. |
| `GOOGLE_API_KEY` | Yes (if using Gemini) | Google Generative AI. |
| `DEEPSEEK_API_KEY` | Yes (if using DeepSeek) | DeepSeek models. |
| `MISTRAL_API_KEY` | Yes (if using Mistral AI) | Mistral models. |
| `XAI_API_KEY` | Yes (if using Grok) | xAI models. |
| `INCEPTION_API_KEY` | Internal Only | JAIS, K2, etc. |
| `INCEPTION_LLAMA3P1_405B_API_KEY` | Internal Only | Llama 3.1‑405B endpoint. |

### SLURM Resources
Modify the header in `run-pipeline.slurm` to match your cluster:

```bash
#SBATCH --job-name=3c3h
#SBATCH --nodes=1
#SBATCH --ntasks-per-node=8
#SBATCH --cpus-per-task=12
#SBATCH --gpus-per-node=8
#SBATCH --mem=800G
#SBATCH --time=14-00:00:00
#SBATCH --partition=your-partition-name
```

### Dataset Batches
Place your evaluation JSON in `tasks/` and specify the task name using the `--task` argument (defaults to AraGen-12-2024-dev).

---

## 📈 Outputs

| Path | Description |
|------|-------------|
| `answers/<task_name>/<org>_<model>_<rev>_<prec>_answers.json` | Raw model completions. |
| `answers/<task_name>/*_answers_judged.json` | Same file after *jury.py* stores judge scores & comments. |
| `results/<task_name>/results__strategy_<vote_or_average>.json` | Aggregated 3C3H & per‑task scores — ready for a leaderboard display. |
| `logs/<task_name>/<SLURM_JOB_ID>/` | Generation & judging stdout/stderr + success/failure model lists. |

---

## 🖇️ Contributing

Pull requests welcome! Please ensure:

- Code is **PEP 8** compliant and typed where practical.
- New dependencies are added to `requirements.txt`.
- Unit tests passed if applicable.

---

## 📜 License

```
Copyright 2025 G42 General Trading LLC

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```
