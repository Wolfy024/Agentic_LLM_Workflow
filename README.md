# LLM Orchestrator

A local coding agent with tool access, REPL interface, and git integration.

## Features

- **Tool-rich**: File system, git, GitHub API, web search, image search, URL fetching, and more
- **REPL interface**: Interactive terminal with slash commands (`/model`, `/help`, etc.)
- **Agent loop**: Autonomous reasoning with tool use, retry logic, and streaming
- **Git-aware**: Full git operations — branches, commits, diffs, blame, remotes, tags
- **Watch mode**: Auto-reload on file changes (auto or batch)
- **Profiles**: `strict`, `dev`, `ci` — control permission behavior
- **Configurable**: API base, model, max tokens, temperature, context window

## Quick Start

```bash
python main.py [workspace_path]
```

### Options

| Flag | Description |
|------|-------------|
| `--model <name>` | Override model selection |
| `--profile <strict\|dev\|ci>` | Set permission profile |
| `--no-stream` | Disable streaming responses |
| `--watch` | Enable file watch mode |
| `--watch-mode <auto\|batch>` | Watch mode strategy |
| `--skip-model-prompt` | Skip interactive model selection |

## Slash Commands

| Command | Description |
|---------|-------------|
| `/help` | Show help |
| `/model` | Change model |
| `/profile` | Switch permission profile |
| `/yolo` | Toggle permissive mode |
| `/watch` | Toggle file watching |
| `/quit` | Exit |

## Project Structure

```
├── main.py              # Entrypoint
├── agent/               # Agent loop, executor, state, file watcher
│   ├── executor.py      # Tool execution with confirmation
│   ├── runner.py        # Main agent loop
│   ├── state.py         # Session state management
│   └── watch/           # File watching service
├── core/                # Bootstrap, config, prefs, permissions
├── llm/                 # LLM client, streaming, error handling
├── repl/                # REPL loop and slash commands
├── tools/               # Tool implementations
│   ├── fs/              # File read, write, edit, search, external
│   ├── git/             # Git operations, GitHub API
│   └── web/             # Web fetch, search
├── ui/                  # Terminal UI, markdown rendering, banners
├── tests/               # Test suite
└── scan.py              # AST scanner (parse + import rules)
```

## Configuration

Set via `.env` file or interactive prompts:

- `ANTHROPIC_API_KEY` — API key
- `ANTHROPIC_API_BASE` — API base URL
- `SERPER_API_KEY` — Web search key (optional)

## Requirements

```
httpx>=0.27.0
rich>=13.7.0
prompt_toolkit>=3.0.43
gitpython>=3.1.42
pathspec>=0.12.1
pytest>=8.0.0
watchdog>=4.0.0
python-dotenv>=1.0.1
```

## License

MIT
