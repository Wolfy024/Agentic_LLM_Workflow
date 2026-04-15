"""MINILLM Boss -- the agentic loop that drives tool-calling conversations."""

from __future__ import annotations
import json
import sys
import os
import time as _time

from prompt_toolkit import prompt
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.formatted_text import HTML

from llm_client import LLMClient, LLMError
from tools import get_tool_schemas, execute_tool, set_workspace, set_serper_key, WORKSPACE
from permissions import ask_permission, set_yolo, is_yolo, _is_destructive
import theme
from theme import console

HISTORY_FILE = os.path.join(os.path.expanduser("~"), ".minillm_history")
SESSIONS_DIR = os.path.join(os.path.expanduser("~"), ".minillm", "sessions")
CHARS_PER_TOKEN = 3.5


def _estimate_tokens(text: str) -> int:
    return int(len(text) / CHARS_PER_TOKEN)


def _message_tokens(msg: dict) -> int:
    total = 0
    content = msg.get("content") or ""
    total += _estimate_tokens(content)
    for tc in msg.get("tool_calls", []):
        fn = tc.get("function", {})
        total += _estimate_tokens(fn.get("name", ""))
        args = fn.get("arguments", "")
        total += _estimate_tokens(args if isinstance(args, str) else json.dumps(args))
    return total + 4


def _resolve_env(value: str) -> str:
    """Resolve 'env:VAR_NAME' strings to environment variable values."""
    if isinstance(value, str) and value.startswith("env:"):
        var_name = value[4:]
        env_val = os.environ.get(var_name)
        if not env_val:
            console.print(theme.warning(
                f"  env var {var_name} not set -- "
                f"set it or put the key directly in config.json"
            ))
            return ""
        return env_val
    return value


def _load_dotenv():
    """Load .env file from the script directory if it exists."""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip()
            if val and val[0] in ('"', "'") and val[-1] == val[0]:
                val = val[1:-1]
            if key not in os.environ:
                os.environ[key] = val


class Agent:
    def __init__(self, config: dict):
        self.context_window = config.get("context_window", 262144)
        self.max_output = config.get("max_tokens", 131072)
        self.verbose = False

        def _on_retry(attempt, max_retries, error_msg, wait):
            console.print(theme.warning(
                f"  retry {attempt}/{max_retries}: {error_msg} "
                f"(waiting {wait:.0f}s)"
            ))

        self.llm = LLMClient(
            api_base=config["api_base"],
            api_key=config["api_key"],
            model=config["model"],
            max_tokens=self.max_output,
            temperature=config.get("temperature", 0.15),
            context_window=self.context_window,
            on_retry=_on_retry,
        )
        self.system_prompt = config.get("system_prompt", "You are a helpful coding assistant with tools.")
        self.messages: list[dict] = [{"role": "system", "content": self.system_prompt}]
        self.tool_schemas = get_tool_schemas()
        self.tool_call_count = 0
        self.max_iterations = 25
        self._tool_schema_tokens = _estimate_tokens(json.dumps(self.tool_schemas))

    def _context_used(self) -> int:
        msg_tokens = sum(_message_tokens(m) for m in self.messages)
        return msg_tokens + self._tool_schema_tokens

    def _context_remaining(self) -> int:
        return self.context_window - self._context_used() - self.max_output

    def _auto_compact(self):
        used = self._context_used()
        limit = self.context_window - self.max_output
        pct = used / limit if limit > 0 else 1.0
        if pct < 0.80 or len(self.messages) <= 4:
            return

        summary_prompt = (
            "Summarize the conversation so far in 2-3 sentences. "
            "Focus on: what the user asked for, what tools were used, "
            "and what decisions were made. Be concise."
        )
        try:
            summary_resp = self.llm.chat([
                {"role": "system", "content": "You are a summarizer. Be extremely concise."},
                {"role": "user", "content": summary_prompt + "\n\nConversation:\n" +
                 "\n".join(
                     f"{m['role']}: {(m.get('content') or '')[:200]}"
                     for m in self.messages[1:10]
                 )},
            ])
            summary = summary_resp["choices"][0]["message"].get("content", "")
        except Exception:
            summary = ""

        before = len(self.messages)
        keep_end = max(6, len(self.messages) // 3)
        self.messages = self.messages[:1] + self.messages[-keep_end:]

        if summary:
            self.messages.insert(1, {
                "role": "system",
                "content": f"[Earlier conversation summary: {summary}]"
            })

        freed = before - len(self.messages)
        new_pct = self._context_used() / limit
        theme.print_auto_compact(freed, pct, new_pct)

    def _run_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        results = []
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]

            raw_args = fn.get("arguments", "")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError as e:
                theme.print_tool_call(name, {"_raw": raw_args[:100]})
                error_msg = json.dumps({
                    "error": f"Malformed JSON in tool arguments: {e}. "
                             f"Raw: {raw_args[:200]}. Please retry with valid JSON."
                })
                theme.print_tool_result(error_msg, success=False)
                results.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": error_msg,
                })
                continue

            theme.print_tool_call(name, args)

            if _is_destructive(name, args):
                if not ask_permission(name, args):
                    theme.print_permission_denied()
                    result = json.dumps({"error": "Permission denied by user."})
                else:
                    theme.print_permission_approved()
                    result = execute_tool(name, args)
            else:
                result = execute_tool(name, args)

            is_error = result.startswith('{"error"') or result.startswith("[exit")
            theme.print_tool_result(result, success=not is_error, verbose=self.verbose)

            results.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": result,
            })
        return results

    def _stream_response(self) -> tuple[str, list[dict]]:
        tool_calls_by_index: dict[int, dict] = {}
        stream_md = theme.StreamingMarkdown()
        started_text = False

        try:
            for chunk in self.llm.chat_stream(self.messages, tools=self.tool_schemas):
                if not chunk.get("choices"):
                    continue

                delta = chunk["choices"][0].get("delta", {})

                content_piece = delta.get("content")
                if content_piece:
                    if not started_text:
                        stream_md.start()
                        started_text = True
                    stream_md.feed(content_piece)

                tc_deltas = delta.get("tool_calls", [])
                for tc_delta in tc_deltas:
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {
                            "id": tc_delta.get("id", f"call_{idx}"),
                            "type": "function",
                            "function": {"name": "", "arguments": ""},
                        }
                    tc = tool_calls_by_index[idx]
                    if tc_delta.get("id"):
                        tc["id"] = tc_delta["id"]
                    fn_delta = tc_delta.get("function", {})
                    if fn_delta.get("name"):
                        tc["function"]["name"] += fn_delta["name"]
                    if fn_delta.get("arguments"):
                        tc["function"]["arguments"] += fn_delta["arguments"]

        except LLMError as e:
            if started_text:
                stream_md.finish()
            theme.print_error(str(e))
            return stream_md._buffer if started_text else "", []
        except Exception as e:
            if started_text:
                stream_md.finish()
            theme.print_error(str(e))
            return stream_md._buffer if started_text else "", []

        full_text = ""
        if started_text:
            full_text = stream_md.finish()

        tool_calls = [tool_calls_by_index[i] for i in sorted(tool_calls_by_index)]
        return full_text, tool_calls

    def chat(self, user_input: str):
        self.messages.append({"role": "user", "content": user_input})
        self.tool_call_count = 0
        self._auto_compact()

        while True:
            remaining = self._context_remaining()
            if remaining < 2000:
                console.print(theme.warning("  context nearly full, compacting..."))
                self._auto_compact()
                if self._context_remaining() < 2000:
                    theme.print_error("Context exhausted. Use /clear to reset.")
                    return

            text, tool_calls = self._stream_response()

            assistant_msg: dict = {"role": "assistant", "content": text or ""}
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            self.messages.append(assistant_msg)

            if not tool_calls:
                break

            self.tool_call_count += len(tool_calls)
            if self.tool_call_count > self.max_iterations:
                console.print(theme.warning("  tool call limit reached"))
                break

            tool_results = self._run_tool_calls(tool_calls)
            self.messages.extend(tool_results)

        theme.print_token_status(self.context_info())

    def reset(self):
        self.messages = [{"role": "system", "content": self.system_prompt}]
        self.tool_call_count = 0

    def context_info(self) -> dict:
        used = self._context_used()
        return {
            "messages": len(self.messages),
            "tokens_used": used,
            "context_window": self.context_window,
            "max_output": self.max_output,
            "remaining": self.context_window - used - self.max_output,
            "pct_used": f"{used / self.context_window:.1%}",
        }

    def save_session(self, name: str) -> str:
        os.makedirs(SESSIONS_DIR, exist_ok=True)
        path = os.path.join(SESSIONS_DIR, f"{name}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"messages": self.messages, "tool_call_count": self.tool_call_count}, f, indent=2)
        return path

    def load_session(self, name: str) -> str:
        path = os.path.join(SESSIONS_DIR, f"{name}.json")
        if not os.path.exists(path):
            return f"Session not found: {path}"
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.messages = data.get("messages", [])
        self.tool_call_count = data.get("tool_call_count", 0)
        return path

    def list_sessions(self) -> list[str]:
        if not os.path.exists(SESSIONS_DIR):
            return []
        return [f[:-5] for f in sorted(os.listdir(SESSIONS_DIR)) if f.endswith(".json")]


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
    if not os.path.exists(config_path):
        theme.print_error(f"Config not found: {config_path}")
        sys.exit(1)
    try:
        with open(config_path) as f:
            config = json.load(f)
    except json.JSONDecodeError as e:
        theme.print_error(f"Invalid JSON in config.json: {e}")
        sys.exit(1)

    for key in ("api_key", "serper_api_key"):
        if key in config:
            config[key] = _resolve_env(config[key])

    required = ("api_base", "api_key", "model")
    for key in required:
        if not config.get(key):
            theme.print_error(f"Missing required config key: {key}")
            sys.exit(1)

    return config


def main():
    _load_dotenv()
    config = load_config()

    workspace = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
    set_workspace(workspace)

    if config.get("serper_api_key"):
        set_serper_key(config["serper_api_key"])

    theme.print_banner(config, WORKSPACE)

    agent = Agent(config)
    multiline_mode = False

    try:
        history = FileHistory(HISTORY_FILE)
    except Exception:
        history = None

    while True:
        try:
            console.print()
            prompt_str = "  >> " if multiline_mode else "  > "
            user_input = prompt(
                HTML(f"<style fg='#6C63FF' bold='true'>{prompt_str}</style>"),
                history=history,
                auto_suggest=AutoSuggestFromHistory() if history else None,
                multiline=multiline_mode,
            ).strip()
        except (EOFError, KeyboardInterrupt):
            theme.print_goodbye()
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            cmd = user_input.lower().split()[0]
            parts = user_input.split(maxsplit=1)

            if cmd in ("/exit", "/quit", "/q"):
                theme.print_goodbye()
                break

            elif cmd == "/help":
                theme.print_help()

            elif cmd == "/clear":
                agent.reset()
                console.print(theme.success("  conversation cleared"))

            elif cmd == "/tools":
                theme.print_tools(agent.tool_schemas)

            elif cmd == "/context":
                theme.print_context(agent.context_info())

            elif cmd == "/workspace":
                if len(parts) > 1:
                    new_ws = os.path.abspath(parts[1])
                    if os.path.isdir(new_ws):
                        set_workspace(new_ws)
                        console.print(theme.success(f"  workspace -> {new_ws}"))
                    else:
                        theme.print_error(f"Not a directory: {new_ws}")
                else:
                    console.print(theme.label_value("workspace", WORKSPACE))

            elif cmd == "/compact":
                msg_count = len(agent.messages)
                if msg_count > 5:
                    agent._auto_compact()
                    info = agent.context_info()
                    console.print(theme.success(
                        f"  {msg_count} -> {len(agent.messages)} messages ({info['pct_used']} used)"
                    ))
                else:
                    console.print(theme.muted("  conversation is already short"))

            elif cmd == "/yolo":
                set_yolo(True)
                console.print(theme.warning("  YOLO mode ON -- all destructive ops auto-approved"))
                console.print(theme.muted("  use /safe to go back"))

            elif cmd == "/safe":
                set_yolo(False)
                console.print(theme.success("  safe mode restored -- destructive ops require approval"))

            elif cmd == "/verbose":
                agent.verbose = not agent.verbose
                state = "ON" if agent.verbose else "OFF"
                console.print(theme.muted(f"  verbose mode {state}"))

            elif cmd == "/multi":
                multiline_mode = not multiline_mode
                state = "ON (Esc+Enter to send)" if multiline_mode else "OFF"
                console.print(theme.muted(f"  multiline input {state}"))

            elif cmd == "/save":
                name = parts[1] if len(parts) > 1 else f"session_{int(_time.time())}"
                path = agent.save_session(name)
                console.print(theme.success(f"  saved -> {path}"))

            elif cmd == "/load":
                if len(parts) > 1:
                    result = agent.load_session(parts[1])
                    if result.startswith("Session not found"):
                        theme.print_error(result)
                    else:
                        info = agent.context_info()
                        console.print(theme.success(
                            f"  loaded {info['messages']} messages from {result}"
                        ))
                else:
                    sessions = agent.list_sessions()
                    if sessions:
                        console.print(theme.section_header("Saved Sessions"))
                        console.print()
                        for s in sessions:
                            console.print(f"    {theme.secondary(s, bold=False)}")
                        console.print()
                    else:
                        console.print(theme.muted("  no saved sessions"))

            else:
                console.print(theme.muted(f"  unknown command: {cmd}"))
            continue

        agent.chat(user_input)

    agent.llm.close()


if __name__ == "__main__":
    main()
