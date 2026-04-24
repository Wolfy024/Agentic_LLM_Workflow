# 🤖 LLM Orchestrator

<div align="center">

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)
![OpenAI Compatible](https://img.shields.io/badge/OpenAI-compatible-412991?logo=openai&logoColor=white)

**A local, self-hostable coding agent with a rich tool suite, interactive REPL, and a modern web UI.**  
Connects to any OpenAI-compatible LLM API endpoint.

</div>

---

## ✨ Features

| Feature | Details |
|---------|---------|
| 🔌 **OpenAI-compatible** | Works with any API that speaks the OpenAI Chat Completions protocol |
| 🛠️ **50+ tools** | File system, git, GitHub API, web search, image search, Stable Diffusion |
| 👁️ **Multimodal** | Send workspace images to vision-capable models via `/image` |
| 💬 **Interactive REPL** | Terminal interface with rich slash commands |
| ⚡ **Autonomous agent loop** | Parallel tool calls, retry logic, streaming, auto context compaction |
| 🌿 **Full git support** | Branches, commits, diffs, blame, remotes, tags, stash, push/pull |
| 💾 **Session management** | Save, load, export, and auto-save conversation sessions |
| 👁️‍🗨️ **Watch mode** | Auto-reload and re-run on file changes (`auto` or `batch`) |
| 🔒 **Permission profiles** | `strict`, `dev`, `ci` — control agent permissions without confirmation |
| 📋 **Recipes** | Reusable prompt templates from `.minillm/recipes/` |
| 🌐 **Web UI** | Companion landing page and documentation site in `docs/` |

---

## 🚀 Installation

### Windows — Pre-built Installer

Download `orchestrator-setup.exe` from the [releases page](https://github.com/Wolfy024/Agentic_LLM_Workflow/releases) (or the `dist/` folder), run it, and fill in your API credentials. The installer copies the binary to `%LOCALAPPDATA%\LLM_Orchestrator\` and optionally adds it to your `PATH`.

After installation, open a **new** terminal and run:

```
orchestrator [workspace_path]
```

### From Source

```bash
# 1. Clone the repository
git clone https://github.com/Wolfy024/Agentic_LLM_Workflow.git
cd Agentic_LLM_Workflow

# 2. Install dependencies
pip install -r requirements.txt

# 3. Create a .env file
cp .env.example backend/.env   # then edit with your credentials

# 4. Run
python backend/main.py [workspace_path]
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

Create a `.env` file in the `backend/` directory (or your install directory):

```env
LLM_API_KEY=your_api_key_here
LLM_API_BASE=https://your-openai-compatible-endpoint/v1
SERPER_API_KEY=your_serper_key_here   # optional — enables web search
SD_API_BASE=https://your-sd-endpoint  # optional — enables Stable Diffusion image generation
```

### Advanced Settings (`config.json`)

| Key | Default | Description |
|-----|---------|-------------|
| `model` | *(set in config.json)* | Model identifier passed to the API |
| `profile` | `strict` | Permission profile: `strict` \| `dev` \| `ci` |
| `context_window` | `262144` | Context window size in tokens |
| `max_tokens` | `131072` | Max tokens per response |
| `temperature` | `0.15` | Sampling temperature |
| `parallel_tool_calls` | `true` | Enable parallel tool execution |
| `max_tool_calls` | `2000` | Max tool calls per session |
| `request_timeout` | `300` | HTTP request timeout (seconds) |
| `connect_timeout` | `20` | Connection timeout (seconds) |
| `max_retries` | `3` | Max retry attempts on failure |
| `retry_backoff_base` | `2.0` | Exponential backoff base for retries |
| `max_read_size_mb` | `3` | Max file read size in MB |
| `max_image_mb` | `20` | Max image size for vision in MB |
| `max_download_mb` | `100` | Max file download size in MB |
| `auto_compact_pct` | `0.8` | Context usage % at which auto-compact triggers |
| `command_timeout` | `30` | Shell command timeout (seconds) |
| `sd_timeout` | `120` | Stable Diffusion generation timeout (seconds) |
| `max_search_results` | `50` | Max web search results returned |

### Permission Profiles

| Profile | Description |
|---------|-------------|
| `strict` | All destructive actions require user confirmation (default) |
| `dev` | File edits auto-approved; shell commands require confirmation |
| `ci` | All actions auto-approved — suitable for pipelines |

---

## 🏃 Quick Start

```bash
python backend/main.py [workspace_path]
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--model <name>` | Override the model from config |
| `--profile <strict\|dev\|ci>` | Set permission profile |
| `--no-stream` | Disable streaming responses |
| `--watch` | Enable file watch mode |
| `--watch-mode <auto\|batch>` | Watch mode strategy (`auto` re-runs on each change; `batch` waits) |
| `--skip-model-prompt` | Skip interactive model selection at startup |

---

## 💬 Slash Commands

Type any of these in the REPL prompt:

### Session & Display

| Command | Description |
|---------|-------------|
| `/help` | Show the help menu |
| `/tools` | List all available tools |
| `/context` | Show context window token usage |
| `/verbose` | Toggle verbose tool output |
| `/multi` | Toggle multiline input mode |

### Model & Permissions

| Command | Description |
|---------|-------------|
| `/model [name]` | Switch model (prompts if no name given) |
| `/profile [strict\|dev\|ci]` | Switch permission profile |
| `/yolo` | Enable permissive mode — skip all confirmations |
| `/safe` | Re-enable confirmation prompts |
| `/confirm` | Toggle edit confirmation |

### Workspace & Files

| Command | Description |
|---------|-------------|
| `/workspace [path]` | Change the active working directory |
| `/watch [auto\|batch]` | Toggle file watching |
| `/image <file> [instruction]` | Send a workspace image to the model (vision) |

### Sessions

| Command | Description |
|---------|-------------|
| `/save [name]` | Save current conversation session |
| `/load [name]` | Load a saved session |
| `/clear` | Clear conversation history |
| `/compact` | Compact context to save tokens |
| `/export` | Export session to a file |

### Tasks & Recipes

| Command | Description |
|---------|-------------|
| `/task <goal>` | Inject a structured task checklist prompt |
| `/plan` | Inject a planning prompt |
| `/recipe <name>` | Load a reusable prompt recipe from `.minillm/recipes/` |

---

## 🛠️ Tool Reference

All tools are available to the agent automatically. Destructive tools require permission based on the active [profile](#permission-profiles).

### 📁 File System

| Tool | Description |
|------|-------------|
| `read_file` | Read file contents with line numbers; outlines large files |
| `read_json` | Read and parse a JSON file (supports key-path access) |
| `write_file` | Write content to a file (creates parent dirs) ⚠️ |
| `append_to_file` | Append content to the end of a file ⚠️ |
| `delete_file` | Delete a file ⚠️ |
| `move_file` | Move or rename a file ⚠️ |
| `create_directory` | Create a directory and its parents ⚠️ |
| `replace_in_file` | Replace an exact string in a file ⚠️ |
| `patch_file` | Apply multi-block line-range edits to a file ⚠️ |
| `diff_files` | Show a unified diff between two files |
| `list_directory` | List files and directories at any path |
| `tree` | Show a tree view of the directory structure |
| `find_files` | Find files matching a glob pattern recursively |
| `search_files` | Search for a regex pattern across files (like ripgrep) |
| `file_info` | Get file metadata: size, modified time, type, line count |
| `summarize_code` | Extract classes, functions, and imports from a source file |
| `count_tokens_estimate` | Estimate token count for a file or text |
| `view_image` | Read a workspace image for vision-capable models |
| `read_external_file` | Read a file outside the workspace (absolute path) |
| `import_external_file` | Copy an external file into the workspace ⚠️ |

### 🌿 Git

| Tool | Description |
|------|-------------|
| `git_status` | Show working tree status |
| `git_diff` | Show unstaged or staged diff |
| `git_diff_between` | Diff between two refs/commits |
| `git_log` | Show commit history |
| `git_show` | Show a specific commit |
| `git_blame` | Show line-by-line authorship |
| `git_search` | Search commit messages or diffs |
| `git_branch` | List or create branches |
| `git_branch_delete` | Delete a branch ⚠️ |
| `git_checkout` | Checkout a branch or file ⚠️ |
| `git_commit` | Stage files and create a commit ⚠️ |
| `git_stash` | Push, pop, list, show, or drop stashes ⚠️ |
| `git_reset` | Reset HEAD (soft / mixed / hard) ⚠️ |
| `git_tag` | List, create, or delete tags ⚠️ |
| `git_remote` | Manage remote URLs |
| `git_push` | Push commits to a remote ⚠️ |
| `git_pull` | Pull from a remote ⚠️ |
| `git_fetch` | Fetch from a remote |
| `git_clone` | Clone a repository ⚠️ |
| `git_init` | Initialize a new repository ⚠️ |
| `git_credential_check` | Check stored git credentials |
| `github_api` | Call any GitHub REST API endpoint |

### 🌐 Web

| Tool | Description |
|------|-------------|
| `read_url` | Fetch and read a web page or documentation URL |
| `download_url` | Download a file from a URL to disk ⚠️ |
| `web_search` | Google web search via Serper (requires `SERPER_API_KEY`) |
| `web_search_news` | Search for recent news articles via Serper |
| `web_search_images` | Search for images via Serper |

### 🖼️ Image Generation

| Tool | Description |
|------|-------------|
| `generate_image` | Generate an image via Stable Diffusion (requires `SD_API_BASE`) ⚠️ |

### 🖥️ System

| Tool | Description |
|------|-------------|
| `run_command` | Execute a shell command in the workspace ⚠️ |
| `run_diagnostics` | Run a linter/typecheck command (e.g. `ruff check`, `eslint`) |
| `env_info` | Get OS, Python version, git version, current user, and cwd |
| `list_processes` | List running processes (optionally filtered by name) |

> ⚠️ **Destructive** — requires confirmation under the `strict` profile.

---

## 📁 Project Structure

```
Agentic_LLM_Workflow/
├── backend/
│   ├── main.py              # Entrypoint
│   ├── agent/
│   │   ├── runner.py        # Main agent loop (streaming, parallel tool calls)
│   │   ├── executor.py      # Tool execution with permission checks
│   │   ├── state.py         # Session state & context management
│   │   └── watch/           # File watching service
│   ├── core/                # Bootstrap, config loader, permissions, prefs
│   ├── llm/                 # LLM client, streaming, vision, error handling
│   ├── repl/
│   │   ├── loop.py          # REPL input loop
│   │   ├── slash.py         # Slash command dispatcher
│   │   └── commands/        # Individual slash command handlers
│   ├── tools/
│   │   ├── registry.py      # @tool decorator, path resolution, sandboxing
│   │   ├── fs/              # read, write, edit, search, external, image
│   │   ├── git/             # git ops, diff, info, remote sync, GitHub API
│   │   ├── web/             # URL fetch, Serper search
│   │   ├── system.py        # Shell, diagnostics, env, process tools
│   │   └── image_gen.py     # Stable Diffusion image generation
│   ├── ui/                  # Terminal UI, markdown rendering, banners
│   ├── sessions/            # Saved conversation sessions (JSON)
│   └── scan.py              # AST scanner (parse + import rules)
├── config.json              # Default configuration
├── docs/                    # Web UI — landing page and documentation site
├── dist/                    # Pre-built binaries and Windows installer
├── tests/                   # Test suite
├── installer.py             # Windows GUI installer (PyInstaller)
├── requirements.txt         # Python dependencies
└── .env.example             # Environment variable template
```

---

## 📦 Requirements

| Package | Version | Purpose |
|---------|---------|---------|
| `httpx[http2]` | ≥ 0.27.0 | Async HTTP client for LLM and web requests |
| `rich` | ≥ 13.7.0 | Terminal UI, markdown rendering, syntax highlighting |
| `prompt_toolkit` | ≥ 3.0.43 | Interactive REPL with history and completion |
| `gitpython` | ≥ 3.1.42 | Git repository interaction |
| `pathspec` | ≥ 0.12.1 | `.gitignore`-style path matching |
| `watchdog` | ≥ 4.0.0 | File system watch mode |
| `python-dotenv` | ≥ 1.0.1 | `.env` file loading |
| `pytest` | ≥ 8.0.0 | Test suite |
| `pyinstaller` | ≥ 6.0.0 | Windows binary packaging |

Install all dependencies:

```bash
pip install -r requirements.txt
```

---

## 📄 License

[MIT](LICENSE)
