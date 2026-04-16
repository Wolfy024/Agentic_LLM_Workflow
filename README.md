# MINILLM — Local AI Coding Agent

> A local AI coding agent powered by Gemma 4 31B with full tool access — reads, writes, searches, and commits code autonomously inside your workspace.

---

## Overview

MINILLM is an interactive, terminal-based coding agent that connects to an OpenAI-compatible LLM endpoint (defaulting to **Gemma 4 31B**) and gives the model a rich set of tools to work with your local codebase. You describe a task in plain language; the agent reads files, edits code, runs git commands, searches the web, and reports back — all without leaving the terminal.

Key characteristics:
- **Local-first**: runs entirely in your terminal, no cloud IDE or browser required.
- **Tool-native**: the model operates through structured tool calls rather than generating raw shell commands.
- **Sandboxed by default**: all file access is confined to the declared workspace directory.
- **Permission profiles**: destructive operations require explicit approval (`strict` mode) or can be locked out entirely (`ci` mode).

---

## Features

- 📂 **Full filesystem toolset** — read, write, patch, search, and traverse directory trees within the workspace.
- 🔀 **Git integration** — status, diff, log, commit, branch, push/pull, tag, GitHub API calls.
- 🌐 **Web search & URL fetching** — Serper-powered search (web, news, images) and raw URL reads.
- 🖥️ **System tools** — run arbitrary commands, inspect processes, query environment.
- 🖼️ **Vision support** — attach workspace images to the conversation for multimodal models.
- 👁️ **File watcher** — auto-detect workspace changes and trigger follow-up agent turns (`--watch`).
- 📜 **Slash commands** — rich REPL with `/help`, `/tools`, `/context`, `/compact`, `/yolo`, `/save`, `/load`, `/export`, and more.
- 🧩 **Context management** — automatic compaction with summary at 80 % context usage.
- 🔌 **Any OpenAI-compatible endpoint** — llama.cpp, Ollama, LM Studio, vLLM, or a hosted provider.

---

## Architecture

```
Agentic_LLM_Workflow/
├── main.py          # Entry point — argument parsing, REPL loop, slash-command dispatch
├── config.json      # Runtime configuration (API base, model, profile, prompts)
├── requirements.txt # Python dependencies
│
├── agent/           # Core agent logic
│   ├── runner.py    # AgentRunner — drives chat turns and tool call loops
│   ├── executor.py  # ToolExecutor — dispatches tool calls, handles approval flow
│   ├── state.py     # SessionState — message history, context tracking
│   ├── tokens.py    # Token counting / estimation utilities
│   └── watch/       # FileWatchService — workspace change detection
│
├── core/            # Cross-cutting utilities
│   ├── config.py    # config.json loader, env-var resolution, dotenv support
│   ├── prefs.py     # Persistent user preferences (~/.minillm/prefs.json)
│   └── permissions_checks.py  # Permission profiles (strict / dev / ci)
│
├── llm/             # LLM client layer
│   ├── client.py    # LLMClient — chat completions, model listing, retry logic
│   ├── stream.py    # Streaming response handler
│   └── vision.py    # Base64 image embedding for multimodal turns
│
├── tools/           # Tool registry and implementations
│   ├── registry.py  # @tool decorator, workspace sandboxing, execute_tool dispatcher
│   ├── fs/          # read_file, write_file, patch_file, replace_in_file, tree, …
│   ├── git/         # git_status, git_commit, git_push, github_api, …
│   ├── web/         # web_search, read_url (Serper)
│   └── system.py    # run_command, env_info, list_processes, run_diagnostics
│
└── ui/              # Terminal UI
    ├── console.py   # Rich console instance
    ├── banner.py    # Startup banner
    ├── help.py      # /help and /tools renderers, slash-command registry
    └── …            # Palette, dimming, streaming display, markdown rendering
```

---

## Requirements / Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.10 or newer |
| An OpenAI-compatible LLM endpoint | Any (llama.cpp, Ollama, LM Studio, vLLM, hosted API) |
| `MINILLM_API_KEY` env var | Required (may be empty string `""` for unauthenticated local servers) |
| `SERPER_API_KEY` env var | Optional — needed only for web search tools |

---

## Installation

```bash
# 1. Clone the repository
git clone https://github.com/Wolfy024/Agentic_LLM_Workflow.git
cd Agentic_LLM_Workflow

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt
```

---

## Configuration

Configuration lives in **`config.json`** at the project root. The file ships with sensible defaults targeting Gemma 4 31B.

```jsonc
// config.json
{
  "api_base": "https://chat.neuralnote.online/v1",   // OpenAI-compatible endpoint
  "api_key":  "env:MINILLM_API_KEY",                 // resolved from env var
  "model":    "unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL",
  "profile":  "strict",                              // strict | dev | ci
  "context_window": 262144,
  "max_tokens": 131072,
  "temperature": 0.15,
  "serper_api_key": "env:SERPER_API_KEY",            // optional, for web search
  "system_prompt": "You are MINILLM Boss, an expert local coding agent …"
}
```

### Environment Variables

Secrets should **never** be hardcoded in `config.json`. Use the `"env:VAR_NAME"` syntax instead, or place them in a `.env` file in the project root:

```ini
# .env  (never commit this file)
MINILLM_API_KEY=sk-your-api-key-here
SERPER_API_KEY=your-serper-key-here
```

The agent loads `.env` automatically on startup.

### Pointing at a different model or endpoint

Edit `config.json`:

```jsonc
{
  "api_base": "http://localhost:11434/v1",  // Ollama example
  "api_key":  "",
  "model":    "qwen2.5-coder:32b"
}
```

Or pass `--model` at the command line to override without editing the file.

---

## Usage

### Basic startup

```bash
# Start the agent in the current directory
python main.py

# Start with an explicit workspace
python main.py /path/to/my/project

# Override the model
python main.py --model qwen2.5-coder:32b

# Start in CI (read-only) profile
python main.py --profile ci
```

### Command-line options

| Flag | Description |
|---|---|
| `workspace` | Path to the project directory (default: current directory) |
| `--model MODEL` | Model ID to use (overrides config.json) |
| `--profile` | Permission profile: `strict` (default), `dev`, or `ci` |
| `--no-stream` | Disable streaming output |
| `--watch` | Enable the file-watcher service |
| `--watch-mode` | `auto` (immediate follow-up) or `batch` (queue changes) |
| `--skip-model-prompt` | Non-interactively pick the first available model |

### Example session

```
> Summarise all public functions in tools/fs/read.py
> Add a docstring to the read_json function
> Run the tests in the tests/ directory and fix any failures
> git commit -m "docs: add docstrings to fs/read tools"
```

### REPL slash commands

| Command | Description |
|---|---|
| `/help` | Show all commands |
| `/tools` | List every registered tool with descriptions |
| `/context` | Display context-window usage statistics |
| `/workspace [path]` | Show or change the active workspace |
| `/compact` | Summarise and trim conversation history |
| `/clear` | Reset conversation to system prompt only |
| `/model [name\|#]` | List or switch active model |
| `/profile strict\|dev\|ci` | Change permission profile |
| `/yolo` | Auto-approve all destructive operations |
| `/safe` | Restore manual approval for destructive operations |
| `/save [name]` | Save conversation to disk |
| `/load [name]` | Load a saved conversation |
| `/export [file]` | Export conversation to Markdown |
| `/watch [on\|off\|mode\|flush]` | Manage the file-watcher |
| `/image <file> [instruction]` | Attach a workspace image to the next turn |
| `/task <text>` | Inject a structured task-checklist system message |
| `/plan` | Inject a planning-mode system message |
| `/multi` | Toggle multiline input mode |
| `/exit` | Quit |

---

## Tools / MCP Integrations

Tools are registered via a `@tool` decorator in `tools/registry.py` and exposed to the model as OpenAI-style function-call schemas. Every tool call is routed through `ToolExecutor`, which enforces the active permission profile before dispatching.

### Available tool categories

| Category | Tools (examples) |
|---|---|
| **Files** | `read_file`, `write_file`, `replace_in_file`, `patch_file`, `append_to_file`, `move_file`, `delete_file`, `create_directory`, `list_directory`, `tree`, `find_files`, `search_files`, `summarize_code` |
| **Git (local)** | `git_status`, `git_diff`, `git_log`, `git_commit`, `git_checkout`, `git_branch_delete`, `git_reset`, `git_stash`, `git_init`, `git_tag` |
| **Git (remote)** | `git_push`, `git_pull`, `git_fetch`, `git_clone`, `git_remote`, `git_credential_check`, `github_api` |
| **Search & Web** | `web_search`, `web_search_news`, `web_search_images`, `read_url` |
| **System** | `run_command`, `run_diagnostics`, `env_info`, `list_processes` |

> Run `/tools` inside the REPL for a live, categorised listing with lock icons showing which tools require approval.

---

## Safety / Security Notes

### Workspace sandboxing
All file-system tools resolve paths relative to the active workspace and reject any path that escapes it (path-traversal protection). The workspace is set at startup and can be changed with `/workspace`.

### Permission profiles

| Profile | Effect |
|---|---|
| `strict` *(default)* | Reads and in-place edits are permitted freely. Destructive operations — `delete_file`, `git_commit`, `git_push`, `run_command`, and others — pause and prompt for `y` before executing. |
| `dev` | Same as `strict`. |
| `ci` | All mutating tools are blocked outright. Safe for use in automated pipelines. |

### YOLO mode
`/yolo` disables the approval prompt for destructive tools. Use only in isolated environments. `/safe` restores normal behaviour.

### Secrets handling
- API keys are never stored as plain text in `config.json`; use the `"env:VAR"` indirection or a `.env` file.
- Add `.env` to `.gitignore` to prevent accidental commits.
- The agent never logs or transmits your API key beyond the configured endpoint.

---

## Roadmap

- [ ] Plugin / recipe system for reusable prompt workflows
- [ ] Multi-agent orchestration (parallel sub-agents)
- [ ] Persistent vector memory across sessions
- [ ] Native MCP (Model Context Protocol) server support
- [ ] Web UI / browser front-end option
- [ ] First-class support for additional vision models

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository and create a feature branch.
2. Follow the existing code style (no linter config is shipped; match the surrounding code).
3. Add or update tests in `tests/` where applicable.
4. Open a pull request with a clear description of the change and its motivation.

For significant changes, open an issue first to discuss the approach.
