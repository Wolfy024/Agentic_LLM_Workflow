# LLM Orchestrator

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

A local, self-hostable coding agent with a rich tool suite, interactive REPL, and a modern web UI. Connects to any OpenAI-compatible LLM API endpoint.

---

## Features

- **OpenAI-compatible**: Works with any API endpoint that speaks the OpenAI Chat Completions protocol
- **Rich tool suite**: File system operations, git, GitHub API, web search, URL fetching, image search, and Stable Diffusion image generation
- **Multimodal**: Send workspace images to vision-capable models with `/image`
- **Interactive REPL**: Terminal interface with slash commands for model switching, session management, and more
- **Autonomous agent loop**: Parallel tool calls, retry logic, streaming responses, and automatic context compaction
- **Git-aware**: Full git operations — branches, commits, diffs, blame, remotes, tags
- **Session management**: Save, load, export, and auto-save conversation sessions
- **Watch mode**: Auto-reload and re-run on file changes (`auto` or `batch`)
- **Permission profiles**: `strict`, `dev`, `ci` — control what the agent is allowed to do without confirmation
- **Recipes**: Reusable prompt templates loaded from `.minillm/recipes/`
- **Web UI**: A companion landing page / documentation site in `frontend/`

---

## Installation

### Windows — Pre-built Installer

Download `orchestrator-setup.exe` from the [releases page](https://github.com/Wolfy024/Agentic_LLM_Workflow/releases) (or `dist/` folder), run it, and fill in your API credentials. The installer copies the binary to `%LOCALAPPDATA%\LLM_Orchestrator\` and optionally adds it to your `PATH`.

After installation, open a **new** terminal and run:

```
orchestrator [workspace_path]
```

### From Source

```bash
# 1. Clone the repository
git clone https://github.com/Wolfy024/Agentic_LLM_Workflow.git
cd Agentic_LLM_Workflow/backend

# 2. Install dependencies
pip install -r ../requirements.txt

# 3. Create a .env file
cp .env.example .env   # then edit with your credentials

# 4. Run
python main.py [workspace_path]
```

---

## Configuration

Create a `.env` file in the backend directory (or the install directory):

```env
LLM_API_KEY=your_api_key_here
LLM_API_BASE=https://your-openai-compatible-endpoint/v1
SERPER_API_KEY=your_serper_key_here   # optional — enables web search
SD_API_BASE=https://your-sd-endpoint  # optional — enables image generation
```

Advanced settings are controlled via `config.json`:

| Key | Default | Description |
|-----|---------|-------------|
| `model` | *(set in config.json)* | Model identifier passed to the API |
| `profile` | `strict` | Permission profile (`strict` \| `dev` \| `ci`) |
| `context_window` | `262144` | Context window size in tokens |
| `max_tokens` | `131072` | Max tokens per response |
| `temperature` | `0.15` | Sampling temperature |
| `parallel_tool_calls` | `true` (boolean) | Enable parallel tool execution |
| `max_tool_calls` | `2000` | Max tool calls per session |
| `request_timeout` | `300` | HTTP request timeout (seconds) |

---

## Quick Start

```bash
python main.py [workspace_path]
```

### CLI Options

| Flag | Description |
|------|-------------|
| `--model <name>` | Override model selection |
| `--profile <strict\|dev\|ci>` | Set permission profile |
| `--no-stream` | Disable streaming responses |
| `--watch` | Enable file watch mode |
| `--watch-mode <auto\|batch>` | Watch mode strategy |
| `--skip-model-prompt` | Skip interactive model selection |

---

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help menu |
| `/tools` | List all available tools |
| `/context` | Show context window usage |
| `/model [name]` | Switch model |
| `/profile [strict\|dev\|ci]` | Switch permission profile |
| `/yolo` | Toggle permissive mode (skip all confirmations) |
| `/safe` | Re-enable confirmation prompts |
| `/confirm` | Toggle edit confirmation |
| `/verbose` | Toggle verbose tool output |
| `/multi` | Toggle multiline input mode |
| `/watch [auto\|batch]` | Toggle file watching |
| `/workspace [path]` | Change working directory |
| `/save [name]` | Save current session |
| `/load [name]` | Load a saved session |
| `/clear` | Clear conversation history |
| `/compact` | Compact context to save tokens |
| `/export` | Export session to file |
| `/task <goal>` | Inject a structured task checklist |
| `/plan` | Inject a planning prompt |
| `/recipe <name>` | Load a prompt recipe from `.minillm/recipes/` |
| `/image <file> [instruction]` | Send a workspace image to the model |

---

## Project Structure

```
├── backend/
│   ├── main.py              # Entrypoint
│   ├── config.json          # Default configuration
│   ├── agent/               # Agent loop, executor, state, file watcher
│   │   ├── executor.py      # Tool execution with confirmation
│   │   ├── runner.py        # Main agent loop
│   │   ├── state.py         # Session state & context management
│   │   └── watch/           # File watching service
│   ├── core/                # Bootstrap, config loader, permissions, prefs
│   ├── llm/                 # LLM client, streaming, vision, error handling
│   ├── repl/                # REPL loop and slash command dispatcher
│   │   └── commands/        # Individual slash command handlers
│   ├── tools/               # Tool implementations
│   │   ├── fs/              # File read, write, edit, search, external open
│   │   ├── git/             # Git operations, GitHub API
│   │   ├── web/             # Web fetch, search (Serper)
│   │   └── image_gen.py     # Stable Diffusion image generation
│   ├── ui/                  # Terminal UI, markdown rendering, banners
│   ├── sessions/            # Saved conversation sessions
│   └── scan.py              # AST scanner (parse + import rules)
├── frontend/                # Web UI (landing page / docs site)
├── dist/                    # Pre-built binaries and installer
├── tests/                   # Test suite
├── installer.py             # Windows GUI installer
└── requirements.txt         # Python dependencies
```

---

## Requirements

```
httpx[http2]>=0.27.0
rich>=13.7.0
prompt_toolkit>=3.0.43
gitpython>=3.1.42
pathspec>=0.12.1
pytest>=8.0.0
watchdog>=4.0.0
python-dotenv>=1.0.1
pyinstaller>=6.0.0
```

---

## License

MIT
