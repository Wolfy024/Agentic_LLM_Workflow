# 🚀 MINILLM Boss
**The Ultimate Local AI Coding Agent**

MINILLM Boss is a high-performance local coding agent powered by **Gemma 4 31B**. It bridges the gap between LLMs and your local filesystem, providing full MCP (Model Context Protocol) tool access to manage your codebase, handle git workflows, and search the web—all from a single terminal interface.

## ✨ Key Features
- 🛠️ **46+ Powerful Tools** — Full control over files, git, GitHub API, and shell commands.
- 🛡️ **Safety First** — Built-in permission system for destructive operations.
- 🔄 **Agentic Loop** — Autonomous tool chaining to solve complex engineering tasks.
- ⚡ **High Performance** — Real-time streaming, 256K context window, and intelligent compaction.
- 🌐 **Web Integrated** — Live Google search and URL fetching via Serper.
- 🚀 **YOLO Mode** — Toggle manual approvals for rapid development.

## 🛠️ Getting Started

### 1. Installation
```bash
pip install -r requirements.txt
```

### 2. Environment Setup
MINILLM Boss uses a `.env` file or system environment variables to manage secrets. Create a `.env` file in the root directory:

```env
# Your LLM API Key
MINILLM_API_KEY=your_api_key_here

# Your Serper API Key for web search
SERPER_API_KEY=your_serper_key_here
```

| Variable | Description | Required |
| :--- | :--- | :---: |
| `MINILLM_API_KEY` | Bearer token for the LLM API | ✅ |
| `SERPER_API_KEY` | API key for Google Search via Serper | ⚠️ (for web tools) |

### 3. Launch
```bash
# Run in current directory
python agent.py

# Or target a specific project
python agent.py /path/to/your/project
```

## ⌨️ CLI Commands
| Command | Description |
| :--- | :--- |
| `/help` | 📖 Show all available commands |
| `/tools` | 🛠️ List all tools and their lock status |
| `/context` | 📊 Check context window usage |
| `/workspace [path]` | 📂 View or change the active workspace |
| `/compact` | 🧹 Summarize and trim conversation |
| `/clear` | ♻️ Reset the current session |
| `/save [name]` | 💾 Save session to `~/.minillm/sessions/` |
| `/load [name]` | 📂 Load a previous session |
| `/yolo` | ⚡ Auto-approve all destructive operations |
| `/safe` | 🛡️ Restore manual approval mode |
| `/multi` | 📝 Toggle multiline input (Esc+Enter to send) |
| `/verbose` | 🔍 Toggle full tool output display |
| `/exit` | 🚪 Quit the agent |

## 🧰 Toolset Overview
The agent has access to 46 tools categorized by capability:

### 📁 File Management
`read_file`, `write_file`, `append_to_file`, `replace_in_file`, `patch_file`, `delete_file`, `move_file`, `create_directory`, `list_directory`, `find_files`, `search_files`, `file_info`, `tree`, `read_json`, `diff_files`, `summarize_code`, `count_tokens_estimate`.

### 🌿 Git Local
`git_status`, `git_diff`, `git_diff_between`, `git_log`, `git_show`, `git_branch`, `git_branch_delete`, `git_commit`, `git_checkout`, `git_init`, `git_stash`, `git_reset`, `git_search`, `git_blame`.

### ☁️ Git Remote & GitHub
`git_push`, `git_pull`, `git_fetch`, `git_clone`, `git_remote`, `git_tag`, `git_credential_check`, `github_api`.

### 🌐 Web & Search
`web_search`, `web_search_news`, `web_search_images`, `read_url`.

### 💻 System
`run_command`, `env_info`, `list_processes`.

> 🔒 **Locked Tools**: Operations that modify files or state require explicit `y` approval unless `/yolo` is active.

## ⚙️ Configuration
Settings are managed in `config.json`. 
**Pro Tip:** Keep `temperature` at `0.15` for maximum tool-calling reliability.

```json
{
  "api_base": "https://chat.neuralnote.online/v1",
  "api_key": "env:MINILLM_API_KEY",
  "model": "unsloth/gemma-4-31B-it-GGUF:UD-Q4_K_XL",
  "context_window": 262144,
  "max_tokens": 131072,
  "temperature": 0.15,
  "serper_api_key": "env:SERPER_API_KEY"
}
```

## 🏗️ Architecture
- `agent.py` $\rightarrow$ Core loop & CLI
- `llm_client.py` $\rightarrow$ API communication & retries
- `permissions.py` $\rightarrow$ Security gate & YOLO mode
- `theme.py` $\rightarrow$ UI & Markdown rendering
- `tools/` $\rightarrow$ MCP tool implementations

---
*Built for developers who want an AI that actually does the work.*
