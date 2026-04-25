# LLM Orchestrator

![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![License](https://img.shields.io/badge/license-MIT-green)

A **local, self-hostable coding agent** with a rich tool suite, interactive REPL, and autonomous agent loop. Connects to any OpenAI-compatible LLM API endpoint and operates with intelligent file watching, retrieval memory, and permission profiles.

---

## Table of Contents

- [Features](#features)
- [Terminology Glossary](#terminology-glossary)
- [Installation](#installation)
  - [From Source](#from-source)
  - [Windows Pre-built Installer](#windows-pre-built-installer)
- [Configuration](#configuration)
  - [`.env` File](#env-file)
  - [`config.json` Settings](#configjson-settings)
  - [User Preferences](#user-preferences)
- [Quick Start](#quick-start)
- [CLI Options](#cli-options)
- [Slash Commands](#slash-commands)
- [Tool Reference](#tool-reference)
- [MCP Servers](#mcp-servers)
- [Permission Profiles](#permission-profiles)
- [Agent Architecture](#agent-architecture)
- [Retrieval Memory](#retrieval-memory)
- [File Watch Service](#file-watch-service)
- [Session Management](#session-management)
- [Recipes](#recipes)
- [Project Structure](#project-structure)
- [Dependencies](#dependencies)
- [License](#license)

---

## Features

| Feature | Description |
|---------|-------------|
| **OpenAI-Compatible** | Works with any API endpoint that speaks the OpenAI Chat Completions protocol |
| **Autonomous Agent Loop** | Parallel tool calls, streaming responses, retry logic, and automatic context compaction |
| **Rich Tool Suite** | File system, git, GitHub API, web search, URL fetching, image search, and Stable Diffusion generation |
| **Multimodal Vision** | Send workspace images to vision-capable models via `/image` |
| **Interactive REPL** | Terminal interface with `prompt_toolkit` and slash commands |
| **Streaming Output** | Live markdown-rendered responses with SSE streaming |
| **Retrieval Memory** | BM25 + vector embeddings + AST symbol indexing for semantic codebase search |
| **File Watch** | Auto-detect file changes and notify the model (`auto` or `batch` mode) |
| **Permission Profiles** | `strict`, `dev`, `ci` — control what the agent can do without confirmation |
| **Session Management** | Save, load, export, and auto-save conversation sessions |
| **Prompt Recipes** | Reusable prompt templates loaded from `.minillm/recipes/` |
| **MCP Protocol Support** | Native MCP client — plug in external MCP servers (filesystem, Brave Search, Postgres, etc.) via config |
| **Server Health Tracking** | Escalating cooldowns for persistent server failures |
| **Web UI** | Companion documentation site in `docs/` |

---

## Terminology Glossary

| Term | Definition |
|------|------------|
| **Agent Runner** | The main event loop (`AgentRunner`) that orchestrates LLM calls, tool execution, and conversation state |
| **Tool Executor** | The dispatch engine (`ToolExecutor`) that validates, approves, and runs tool calls — supports parallel execution |
| **Session State** | (`SessionState`) Tracks message history, tool call count, and token usage estimates |
| **Slash Command** | A REPL command prefixed with `/` (e.g., `/model`, `/save`) that triggers handler functions |
| **Permission Profile** | A mode (`strict`, `dev`, `ci`) that controls which tools require user approval or are blocked entirely |
| **YOLO Mode** | A permissive mode where all destructive operations (delete, git push, etc.) are auto-approved |
| **Retrieval Memory** | An in-memory index of visited files, extracted symbols, and vector embeddings used for semantic search |
| **File Watch** | A background service (`FileWatchService`) using `watchdog` to monitor workspace file changes |
| **Recipe** | A JSON file in `.minillm/recipes/` containing reusable prompt templates, system prompts, or message payloads |
| **Context Compaction** | The process of reducing conversation history to fit within token limits (handled server-side) |
| **Parallel Tool Calls** | Executing multiple read-only, non-destructive tools concurrently via `ThreadPoolExecutor` |
| **Circuit Breaker** | A safety mechanism that prevents the agent from repeatedly reading the same file section or looping on tool calls |
| **Stream Mode** | Server-Sent Events (SSE) streaming for live token output vs. synchronous full-response mode |
| **Tool Schema** | The OpenAI function-calling JSON schema that describes each tool's name, description, and parameters |
| **Workspace** | The root directory the agent operates within; all relative paths resolve against it |
| **Destructive Tool** | A tool that modifies or deletes state (e.g., `delete_file`, `git_push`, `git_reset`) requiring approval |
| **Health Tracker** | (`ServerHealthTracker`) Monitors consecutive server failures and applies escalating cooldowns |
| **Batch Mode** | A file watch mode where changes are queued and flushed to the model in a single notification |
| **Auto Mode** | A file watch mode where each file change triggers an immediate notification to the model |
| **MCP** | Model Context Protocol — an open standard for connecting LLM agents to external tool servers |
| **MCP Server** | A process that exposes tools/resources over the MCP protocol (stdio subprocess or HTTP/SSE endpoint) |
| **MCP Client** | The orchestrator's built-in client that connects to MCP servers and routes tool calls |
| **Stdio Transport** | MCP communication over stdin/stdout pipes to a local subprocess |
| **SSE Transport** | MCP communication over HTTP Server-Sent Events to a remote server |

---

## Installation

### From Source

```bash
# 1. Clone the repository
git clone https://github.com/Wolfy024/Agentic_LLM_Workflow.git
cd Agentic_LLM_Workflow

# 2. Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create a .env file
cp .env.example .env
# Edit .env with your API credentials (see Configuration below)

# 5. Run the orchestrator
cd backend
python main.py [workspace_path]
```

### Windows Pre-built Installer

1. Download `llm-orchestrator-setup.exe` from the [releases page](https://github.com/Wolfy024/Agentic_LLM_Workflow/releases) (or `dist/` folder)
2. Run the installer — it copies the binary to `%LOCALAPPDATA%\LLM_Orchestrator\` and optionally adds it to your `PATH`
3. Create a `.env` file in the install directory with your credentials
4. Open a **new** terminal and run:

```
orchestrator [workspace_path]
```

---

## Configuration

### `.env` File

Create a `.env` file in the project root (or install directory):

```env
# Required
LLM_API_KEY=your_api_key_here
LLM_API_BASE=https://your-openai-compatible-endpoint/v1

# Required (unless model is set in config.json)
LLM_MODEL=your_model_name_here

# Optional — enables web search via Serper
SERPER_API_KEY=your_serper_key_here

# Optional — enables Stable Diffusion image generation
SD_API_BASE=https://your-sd-endpoint

# Optional — overrides config.json settings
# LLM_MODEL=gpt-4o
```

### `config.json` Settings

Advanced settings are controlled via `config.json` (located in the project root or install directory):

| Key | Default | Description |
|-----|---------|-------------|
| `api_base` | *(env:LLM_API_BASE)* | LLM API endpoint base URL |
| `api_key` | *(env:LLM_API_KEY)* | API authentication key |
| `model` | *(env:LLM_MODEL)* | Model identifier passed to the API |
| `profile` | `strict` | Permission profile (`strict` \| `dev` \| `ci`) |
| `temperature` | `0.15` | Sampling temperature (0.0–1.0) |
| `parallel_tool_calls` | `true` | Enable parallel tool execution |
| `max_tool_calls` | `2000` | Max tool calls per session |
| `max_retries` | `3` | Number of retry attempts per request |
| `retry_backoff_base` | `2.0` | Base for exponential backoff (seconds) |
| `request_timeout` | `300` | HTTP request timeout (seconds) |
| `connect_timeout` | `20` | Connection timeout (seconds) |
| `max_read_size_mb` | `3` | Maximum file read size (MB) |
| `max_image_mb` | `20` | Maximum image file size for vision (MB) |
| `max_download_mb` | `100` | Maximum download size for `download_url` (MB) |
| `context_low_threshold` | `2000` | Token threshold for context warnings |
| `auto_compact_pct` | `0.8` | Compact context at 80% of context window |
| `command_timeout` | `30` | Timeout for `run_command` tool (seconds) |
| `sd_timeout` | `120` | Stable Diffusion API timeout (seconds) |
| `max_search_results` | `50` | Max results for file search tools |
| `diff_preview_limit` | `6000` | Max characters for diff previews |
| `mcp_servers` | `{}` | MCP server definitions (see [MCP Servers](#mcp-servers)) |
| `system_prompt` | *(see config.json)* | Default system prompt for the agent |
| `sd_api_base` | *(env:SD_API_BASE)* | Stable Diffusion API endpoint |
| `serper_api_key` | *(env:SERPER_API_KEY)* | Serper API key for web search |

### User Preferences

User preferences are stored in `~/.minillm/preferences.json` and persist across sessions:

| Preference | Default | Description |
|------------|---------|-------------|
| `workspace` | Current directory | Last used workspace path |
| `model` | *(from config)* | Last used model |
| `profile` | `strict` | Last used permission profile |
| `yolo` | `false` | Whether YOLO mode was active |
| `verbose` | `false` | Whether verbose tool output is enabled |
| `confirm_edits` | `true` | Whether to show edit diff previews |
| `watch_enabled` | `false` | Whether file watch was active |
| `watch_mode` | `auto` | File watch mode (`auto` or `batch`) |
| `last_session_name` | — | Last loaded session name |

---

## Quick Start

```bash
cd backend
python main.py /path/to/your/project
```

Once the REPL starts:

1. **Type a prompt** and press Enter — the agent will think, use tools, and respond
2. **Use slash commands** to control the agent (see below)
3. **Press Ctrl+C** to interrupt a streaming response

---

## CLI Options

| Flag | Description |
|------|-------------|
| `workspace` | Workspace directory (positional argument) |
| `--model <name>` | Override model selection |
| `--profile <strict\|dev\|ci>` | Set permission profile |
| `--no-stream` | Disable streaming responses (use synchronous mode) |
| `--watch` | Enable file watch mode at startup |
| `--watch-mode <auto\|batch>` | Set watch mode strategy |
| `--skip-model-prompt` | Skip interactive model selection |

---

## Slash Commands

All slash commands are entered in the REPL. They are prefixed with `/`.

### Info & Display

| Command | Description |
|---------|-------------|
| `/help` | Show the help menu with all available commands |
| `/tools` | List all registered tools with descriptions |
| `/context` | Display token usage stats (messages, tokens used, source) |
| `/memory` | Display retrieval memory stats (visited files, symbols, vector docs) |

### Configuration

| Command | Description |
|---------|-------------|
| `/model [name]` | List available models or switch to a specific model. Use `/model <index>` or `/model <substring>` |
| `/profile [strict\|dev\|ci]` | Show or switch permission profile |
| `/workspace [path]` | Show or change the workspace directory |
| `/yolo` | Enable YOLO mode — all destructive ops auto-approved |
| `/safe` | Restore manual approval for destructive ops |
| `/verbose` | Toggle verbose tool output |
| `/confirm` | Toggle edit diff preview before applying changes |
| `/multi` | Toggle multiline input mode (for multi-line prompts) |

### Session Management

| Command | Description |
|---------|-------------|
| `/save [name]` | Save current session to disk with an optional name |
| `/load [name]` | Load a saved session. Use `/load` alone to list available sessions, or `/load <number>` |
| `/clear` | Reset conversation history (keeps system prompt) |
| `/compact` | Compact context to save tokens (server-side) |
| `/export [filename]` | Export conversation to a markdown file |

### Context Injection

| Command | Description |
|---------|-------------|
| `/task <goal>` | Inject a structured task checklist into context |
| `/plan` | Inject a planning prompt (read-before-write mode) |
| `/recipe <name>` | Load a prompt recipe from `.minillm/recipes/<name>.json` |
| `/image <file> [instruction]` | Send a workspace image to a multimodal model |

### File Watch

| Command | Description |
|---------|-------------|
| `/watch` | Show watch status |
| `/watch on` | Enable file watch (auto mode) |
| `/watch off` | Disable file watch |
| `/watch mode auto\|batch` | Set watch mode strategy |
| `/watch flush` | Flush queued file changes to the model immediately |

### MCP

| Command | Description |
|---------|-------------|
| `/mcp` | Show MCP server status (connected servers and tool counts) |
| `/mcp connect` | Re-connect all MCP servers from `config.json` |
| `/mcp disconnect` | Disconnect all MCP servers |
| `/mcp status` | Detailed status including per-server tool lists |

### Exit

| Command | Description |
|---------|-------------|
| `/exit`, `/quit`, `/q` | Exit the REPL (auto-saves session) |

---

## Tool Reference

### File System Tools

| Tool | Destructive | Description |
|------|:-----------:|-------------|
| `read_file` | No | Read file contents with line numbers. Supports `offset`/`limit` for large files. Returns structural outline for files >250 lines |
| `read_json` | No | Parse a JSON file with optional dot-separated key path extraction |
| `list_directory` | No | List files and directories at any path |
| `tree` | No | Show a tree view of the directory structure with configurable depth |
| `write_file` | Yes | Write content to a file. Creates parent directories if needed |
| `append_to_file` | Yes | Append content to the end of a file (creates it if missing) |
| `delete_file` | Yes | Delete a file |
| `move_file` | Yes | Move/rename a file |
| `create_directory` | Yes | Create a directory (and parent directories) |
| `replace_in_file` | Yes | Replace an exact string in a file. Supports `replace_all` flag |
| `patch_file` | Yes | Apply multi-block line-range edits to a file |
| `diff_files` | No | Show a unified diff between two files |
| `file_info` | No | Get file metadata (size, modified time, type, line count) |
| `download_url` | No | Download a file from a URL into the workspace |
| `read_external_file` | No | Read a text file from an absolute path outside the workspace |
| `import_external_file` | No | Copy a file from outside the workspace into the workspace |
| `generate_image` | No | Generate an image using Stable Diffusion from a text prompt |
| `view_image` | No | View an image file and send it to the model for analysis |

### Git Tools

| Tool | Destructive | Description |
|------|:-----------:|-------------|
| `git_status` | No | Show working tree status |
| `git_log` | No | Show recent commit history |
| `git_diff` | No | Show unstaged or staged diffs |
| `git_diff_between` | No | Show diff between two branches, tags, or commits |
| `git_branch` | No | List branches or show current branch |
| `git_tag` | No | List or create git tags |
| `git_remote` | No | Show or manage git remotes |
| `git_commit` | Yes | Stage files and commit |
| `git_checkout` | Yes | Checkout a branch, file, or commit |
| `git_stash` | Yes | Stash or pop working directory changes |
| `git_reset` | Yes | Reset current HEAD to a target state |
| `git_push` | Yes | Push commits to a remote |
| `git_pull` | Yes | Pull changes from a remote |
| `git_fetch` | No | Fetch refs from a remote |
| `git_clone` | Yes | Clone a repository |
| `git_search` | No | Search git history for a pattern |
| `git_blame` | No | Show git blame for a file |
| `git_show` | No | Show the content of a specific commit |
| `github_api` | Conditional | Call the GitHub API via the `gh` CLI |

### Search & Analysis Tools

| Tool | Destructive | Description |
|------|:-----------:|-------------|
| `search_files` | No | Search for a text pattern (regex) across files |
| `find_files` | No | Find files matching a glob pattern recursively |
| `smart_context_search` | No | Parallel retrieval pipeline with BM25 keyword scoring, AST symbol lookup, and vector embeddings |
| `summarize_code` | No | Extract the structure of a source file: classes, functions, imports |
| `count_tokens_estimate` | No | Rough token count estimate for a file or text |

### Web Tools

| Tool | Destructive | Description |
|------|:-----------:|-------------|
| `web_search` | No | Search the web using Google (via Serper API) |
| `web_search_news` | No | Search for recent news articles (via Serper) |
| `web_search_images` | No | Search for images on a topic (via Serper) |
| `read_url` | No | Fetch and read a URL (documentation, web page) |

### System Tools

| Tool | Destructive | Description |
|------|:-----------:|-------------|
| `run_command` | Yes | Execute a shell command in the workspace |
| `env_info` | No | Get environment info: OS, Python version, git version |
| `list_processes` | No | List running processes (optionally filtered) |

---

## MCP Servers

The orchestrator includes a native **MCP (Model Context Protocol)** client that lets you plug in external tool servers without writing any code. MCP tools appear alongside native tools — the LLM sees them as a single unified toolset.

### Adding MCP Servers

Add entries to the `mcp_servers` key in `config.json` (works both from source and post-install — just edit the `config.json` next to the executable):

```json
{
  "mcp_servers": {
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/path/to/allowed/dir"],
      "permission": "destructive"
    },
    "brave-search": {
      "transport": "sse",
      "url": "https://your-mcp-proxy.example.com",
      "headers": { "Authorization": "Bearer your_key" },
      "permission": "allow"
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://localhost/mydb"],
      "permission": "destructive"
    }
  }
}
```

### Transport Types

| Transport | Use Case | Config Keys |
|-----------|----------|-------------|
| `stdio` (default) | Local subprocess MCP servers (filesystem, git, Postgres) | `command`, `args`, `env`, `cwd` |
| `sse` | Remote HTTP MCP servers (Brave Search, API gateways) | `url`, `headers` |

### Permission Levels

Each MCP server has a `permission` setting that controls how the orchestrator gates its tools:

| Permission | Behavior |
|------------|----------|
| `"allow"` | Tools run freely (like native read-only tools) |
| `"destructive"` (default) | Tools require user approval before execution (unless YOLO mode) |
| `"deny"` | Tools are registered but blocked from execution |

In `ci` profile, **all** MCP tools are blocked regardless of their permission setting.

### Lifecycle

1. **Startup** — MCP servers defined in config are auto-connected when the orchestrator launches
2. **Runtime** — Use `/mcp connect` to reconnect, `/mcp disconnect` to tear down
3. **Shutdown** — All MCP servers are gracefully disconnected on exit

### Post-Install Setup

After installing via the pre-built executable:

1. Navigate to the install directory (e.g., `%LOCALAPPDATA%\LLM_Orchestrator\`)
2. Open `config.json` in any text editor
3. Add your MCP server entries to the `mcp_servers` object
4. Restart the orchestrator — servers will auto-connect

> **Note:** Most MCP servers require `npx` (Node.js) to be installed on your system. Install Node.js from [nodejs.org](https://nodejs.org/) if you haven't already.

---

## Permission Profiles

The orchestrator supports three permission profiles that control tool access and approval requirements:

### `strict` (Default)

- All destructive tools require explicit user approval
- Edit tools (`replace_in_file`, `patch_file`) show a diff preview before applying
- All tools are available

### `dev`

- Same as `strict` — designed for development workflows
- Destructive tools require approval
- Edit previews are shown

### `ci`

- Mutating tools are **blocked** entirely (cannot modify files)
- Read-only tools are allowed
- `list_directory` outside workspace is blocked
- `git_remote add/remove`, `git_tag create/delete`, and non-GET `github_api` calls are blocked

### Destructive Tools

The following tools are always flagged as destructive and require approval (unless YOLO mode is active):

| Category | Tools |
|----------|-------|
| File operations | `delete_file`, `write_file`, `append_to_file`, `move_file`, `create_directory` |
| Git operations | `git_init`, `git_commit`, `git_checkout`, `git_branch_delete`, `git_reset`, `git_stash`, `git_push`, `git_pull`, `git_clone` |
| External | `read_external_file`, `import_external_file`, `run_command` |
| Conditional | `github_api` (non-GET), `git_tag` (create/delete), `git_remote` (add/remove) |

---

## Agent Architecture

```
┌─────────────────────────────────────────────────────┐
│                    REPL Loop                         │
│  (prompt_toolkit interactive shell)                  │
└────────────────┬────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────┐
│                  AgentRunner                         │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐ │
│  │  Stream /    │  │  LLMClient   │  │ Session    │ │
│  │  Sync Call   │  │ (httpx)      │  │ State      │ │
│  └──────┬──────┘  └──────┬───────┘  └────┬───────┘ │
│         │                │                │         │
│         ▼                ▼                │         │
│  ┌─────────────────────────────────────────────┐  │
│  │           ToolExecutor                      │  │
│  │  ┌────────────┐  ┌──────────────────────┐   │  │
│  │  │ Parallel   │  │ Permission Checks    │   │  │
│  │  │ Batch      │  │ (Profile + Destruct) │   │  │
│  │  └─────┬──────┘  └──────────────────────┘   │  │
│  └────────┼────────────────────────────────────┘  │
│           │                                       │
│           ▼                                       │
│  ┌────────────────────────────────────────────┐   │
│  │         Tool Registry                      │   │
│  │  FS · Git · Web · Search · System · MCP    │   │
│  └─────────────────┬──────────────────────────┘   │
│                    │                              │
│                    ▼                              │
│  ┌────────────────────────────────────────────┐   │
│  │         MCP Client Bridge                  │   │
│  │  stdio (local) · SSE (remote)              │   │
│  │  → filesystem · brave-search · postgres    │   │
│  └────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────┘
```

### Key Components

| Component | File | Role |
|-----------|------|------|
| **AgentRunner** | `backend/agent/runner.py` | Main event loop — orchestrates LLM calls, streaming, tool execution, and circuit breaker |
| **ToolExecutor** | `backend/agent/executor.py` | Dispatch engine — validates, approves, and runs tool calls with parallel execution support |
| **SessionState** | `backend/agent/state.py` | Tracks message history, tool call count, and token usage |
| **LLMClient** | `backend/llm/client.py` | HTTP client for API calls with retry logic and health tracking |
| **ServerHealthTracker** | `backend/llm/errors.py` | Monitors consecutive failures and applies escalating cooldowns |
| **ToolRegistry** | `backend/tools/registry.py` | Decorator-based tool registration with OpenAI function-calling schemas |
| **MCPManager** | `backend/mcp/manager.py` | Multi-server MCP lifecycle, schema aggregation, and tool routing |
| **MCPClient** | `backend/mcp/client.py` | Per-server client — handles initialize, tool discovery, tool execution |
| **FileWatchService** | `backend/agent/watch/service.py` | Background file monitoring via `watchdog` |

### Retry Logic

The LLM client implements a robust retry system:

1. **Pre-request cooldown** — If the server has had consecutive failures, an escalating cooldown is applied (2s → 5s → 10s → 20s → 30s cap)
2. **Retry loop** — Up to `max_retries` (default: 3) attempts with exponential backoff (`backoff_base ^ attempt`)
3. **Error classification** — Errors are classified as retryable (429, 5xx, timeouts, connection errors) or non-retryable (401, 403, 404)
4. **Health tracking** — Consecutive 5xx/timeout failures are tracked globally; after 3 failures, the server is marked unhealthy

---

## Retrieval Memory

The orchestrator maintains an intelligent index of the workspace for semantic codebase search:

### What It Tracks

| Index Type | Description |
|------------|-------------|
| **Visited Files** | Every file read by the agent is tracked with its full content and line count |
| **AST Symbols** | Classes, functions, methods, imports, and other symbols extracted via AST parsing (Python) or regex (other languages) |
| **Vector Embeddings** | File content is embedded using `sentence-transformers` for semantic similarity search |
| **BM25 Keywords** | Keyword scoring for fast text matching across file contents |

### How It Works

1. When a file is read, it's automatically tracked via `track_file()`
2. Symbols are extracted using `tree-sitter` (Python) or regex patterns (other languages)
3. Content is embedded into vector space for semantic search
4. `smart_context_search()` combines BM25 keyword scoring, symbol lookup, and vector similarity to find relevant code

### Checking Memory

Use `/memory` in the REPL to see:
- Number of visited files
- Important symbols indexed
- Summaries created
- Vector documents indexed
- Memory file and vector index file paths

---

## File Watch Service

The file watch service monitors the workspace for changes and notifies the agent:

### Modes

| Mode | Behavior |
|------|----------|
| `auto` | Each file change triggers an immediate notification to the model |
| `batch` | Changes are queued and flushed to the model in a single notification |

### Usage

```
/watch on              — Enable file watch
/watch off             — Disable file watch
/watch mode auto       — Set auto mode
/watch mode batch      — Set batch mode
/watch flush           — Flush queued changes immediately
/watch status          — Show current status
```

### Ignoring Files

Create a `.minillm/watch_ignore` file in your workspace to specify paths to ignore (uses `pathspec` patterns).

---

## Session Management

Sessions are saved as JSON files in the `sessions/` directory within your workspace.

### Saving

```
/save [name]           — Save with optional name
```

Sessions are also **auto-saved** when you exit via `/exit`, `/quit`, or `/q` (if there's actual conversation history).

### Loading

```
/load                  — List all saved sessions
/load <number>         — Load by session number
/load <name>           — Load by session name
```

### Exporting

```
/export [filename]     — Export conversation to a markdown file
```

### Session File Format

```json
{
  "messages": [...],
  "tool_call_count": 42,
  "model": "gpt-4o",
  "system_prompt": "...",
  "retrieval_memory": {...}
}
```

---

## Recipes

Recipes are reusable prompt templates stored as JSON files in `.minillm/recipes/` (in your workspace or `~/.minillm/`).

### Recipe Format

A recipe JSON can contain:

| Field | Description |
|-------|-------------|
| `prompt` | A prompt to send to the model |
| `system` | A system prompt to inject |
| `user` | A user message to inject |
| `messages` | A list of messages to inject |

### Loading

```
/recipe <name>         — Load .minillm/recipes/<name>.json
```

---

## Project Structure

```
├── backend/
│   ├── main.py                    # Entrypoint — ties together core loops, LLM client, UI, tools
│   ├── config.json                # Default configuration
│   ├── agent/
│   │   ├── runner.py              # Main agent event loop
│   │   ├── executor.py            # Tool dispatch with parallel execution
│   │   ├── state.py               # Session state & context management
│   │   ├── tokens.py              # Token estimation utilities
│   │   └── watch/                 # File watch service
│   │       ├── service.py         # Watchdog observer integration
│   │       ├── state.py           # Watch state management
│   │       └── utils.py           # Pathspec loading, event handling
│   ├── core/
│   │   ├── bootstrap.py           # Startup: interactive model selection
│   │   ├── cache.py               # Model caching utilities
│   │   ├── config.py              # Config loading, .env resolution
│   │   ├── permissions_checks.py  # Profile logic, destructive tool detection
│   │   ├── permissions_prompts.py  # Approval prompts, YOLO mode
│   │   ├── prefs.py               # User preferences (save/load)
│   │   ├── repl_utils.py          # REPL utilities (safe names, recipes)
│   │   └── runtime_config.py      # Runtime config accessor
│   ├── llm/
│   │   ├── client.py              # HTTP client, retry logic, health tracking
│   │   ├── errors.py              # Error classification, ServerHealthTracker
│   │   ├── stream.py              # SSE streaming integration
│   │   └── vision.py              # Multimodal image content builder
│   ├── repl/
│   │   ├── __init__.py            # REPL loop entry point
│   │   ├── slash.py               # Slash command dispatcher
│   │   ├── commands/              # Individual command handlers
│   │   │   ├── __init__.py        # COMMAND_DISPATCH registry
│   │   │   ├── config.py          # /model, /profile, /workspace, /yolo, etc.
│   │   │   ├── info.py            # /help, /tools, /context, /memory
│   │   │   ├── inject.py          # /task, /plan, /recipe, /image
│   │   │   ├── session.py         # /save, /load, /clear, /compact, /export
│   │   │   ├── watch.py           # /watch subcommands
│   │   │   └── mcp.py             # /mcp subcommands
│   │   ├── loop.py                # REPL input loop
│   │   └── slash_complete.py      # Slash command autocompletion
│   ├── tools/
│   │   ├── registry.py            # @tool decorator, workspace, execution engine
│   │   ├── fs/                    # File system tools
│   │   │   ├── read.py            # read_file, read_json, list_directory, tree
│   │   │   ├── write.py           # write_file, append_to_file, delete_file, etc.
│   │   │   ├── edit.py            # replace_in_file, patch_file, diff_files
│   │   │   ├── search.py          # search_files, find_files, smart_context_search
│   │   │   ├── image.py           # Image generation utilities
│   │   │   └── external.py        # read_external_file, import_external_file
│   │   ├── git/                   # Git tools
│   │   │   ├── core.py            # GitPython wrapper
│   │   │   ├── diff.py            # Diff operations
│   │   │   ├── github.py          # GitHub API integration
│   │   │   ├── info.py            # Status, log, branch, tag operations
│   │   │   ├── ops.py             # Commit, checkout, stash, reset
│   │   │   └── remote_sync.py     # Push, pull, fetch, clone
│   │   ├── web/                   # Web tools
│   │   │   ├── serper.py          # Web search, news, images via Serper
│   │   │   └── fetch.py           # URL fetching, download_url
│   │   ├── image_gen.py           # Stable Diffusion image generation
│   │   └── system.py              # run_command, env_info, list_processes
│   ├── mcp/                       # MCP (Model Context Protocol) client
│   │   ├── __init__.py            # Package init
│   │   ├── transport.py           # Stdio + SSE JSON-RPC transports
│   │   ├── client.py              # Per-server MCP client
│   │   └── manager.py             # Multi-server manager singleton
│   ├── ui/
│   │   ├── banner.py              # Startup banner
│   │   ├── components.py          # UI components (label_value, etc.)
│   │   ├── console.py             # Rich console wrapper
│   │   ├── context_logs.py        # Context/error/success message printing
│   │   ├── dimming.py             # Muted/dimmed text styling
│   │   ├── help.py                # Help menu, model listing
│   │   ├── markdown.py            # Markdown rendering
│   │   ├── palette.py             # Color palette definitions
│   │   ├── repl_bindings.py       # REPL key bindings
│   │   ├── streaming.py           # Streaming markdown renderer
│   │   └── tool_logs.py           # Tool call/result display
│   └── sessions/                  # Saved conversation sessions
├── docs/                          # Web UI / documentation site
│   ├── index.html
│   ├── css/styles.css
│   └── js/
├── dist/                          # Pre-built binaries and installer
├── tests/                         # Test suite
├── entrypoint.py                  # Alternative entrypoint
├── installer.py                   # Windows GUI installer
├── requirements.txt               # Python dependencies
└── .env.example                   # Example environment configuration
```

---

## Dependencies

```
httpx[http2]>=0.27.0          # HTTP client with HTTP/2 support
rich>=13.7.0                  # Rich terminal formatting
prompt_toolkit>=3.0.43        # Interactive REPL shell
gitpython>=3.1.42             # Git operations
pathspec>=0.12.1              # .gitignore-style path matching
pytest>=8.0.0                 # Testing framework
watchdog>=4.0.0               # File system monitoring
python-dotenv>=1.0.1          # .env file loading
pyinstaller>=6.0.0            # Binary packaging
tree-sitter>=0.22.0           # AST parsing for code analysis
tree-sitter-languages>=1.10.2 # Language grammars for tree-sitter
sentence-transformers>=3.0.0  # Vector embeddings for semantic search
```

---

## License

MIT
