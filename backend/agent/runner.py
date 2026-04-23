"""
Agent main event loop.

Orchestrates the synchronous completion rounds, streaming generation, 
and tool evaluation chains for the LLM interactive shell.
"""

from __future__ import annotations
import json
from tools.fs.image import IMAGE_MARKER
from ui.streaming import StreamingMarkdown
from ui.context_logs import print_error, print_token_status
from ui.tool_logs import print_tool_call, print_tool_result
from ui.palette import warning
from ui.console import console
from llm.client import LLMClient
from llm.errors import LLMError
from llm.stream import stream_chat
from agent.state import SessionState
from agent.executor import ToolExecutor
import core.runtime_config as rc

# Magic number constants — read from config at runtime
def _context_low_threshold() -> int:
    return int(rc.get("context_low_threshold", 2000))

CONTEXT_LOW_THRESHOLD = 2000  # module-level default

# Keys used by tool schemas for file path arguments
_FILE_TARGET_KEYS = ("path", "file", "file_a", "TargetFile", "AbsolutePath",
                     "SearchPath", "DirectoryPath", "url", "Url")
# Keys that differentiate reading sections of the same file
_RANGE_KEYS = ("offset", "limit", "start_line", "end_line", "key_path", "pattern")


class AgentRunner:
    def __init__(self, state: SessionState, llm: LLMClient, executor: ToolExecutor, stream: bool = True):
        self.state = state
        self.llm = llm
        self.executor = executor
        self.stream = stream
        self.max_iterations = 50
        self._tool_history: list[tuple] = []  # (tool_name, file_target, range_key) tuples

    @staticmethod
    def _normalize_stream_content(raw) -> str:
        """Turn delta/message content into a string (handles multimodal list shapes)."""
        if raw is None:
            return ""
        if isinstance(raw, str):
            return raw
        if isinstance(raw, list):
            parts: list[str] = []
            for item in raw:
                if isinstance(item, dict):
                    if item.get("type") == "text" and "text" in item:
                        parts.append(str(item["text"]))
                    elif "text" in item:
                        parts.append(str(item["text"]))
                elif isinstance(item, str):
                    parts.append(item)
            return "".join(parts)
        return str(raw)

    def _stream_response(self) -> tuple[str, list[dict]]:
        tool_calls_by_index: dict[int, dict] = {}
        stream_md = StreamingMarkdown()
        started_text = False

        try:
            for chunk in stream_chat(self.llm, self.state.messages, tools=self.state.tool_schemas):
                if not chunk.get("choices"):
                    continue

                choice0 = chunk["choices"][0]
                delta = choice0.get("delta") or {}
                content_piece = self._normalize_stream_content(delta.get("content"))
                if not content_piece:
                    content_piece = self._normalize_stream_content((choice0.get("message") or {}).get("content"))
                if content_piece:
                    if not started_text:
                        stream_md.start()
                        started_text = True
                    stream_md.feed(content_piece)

                tc_deltas = delta.get("tool_calls", [])
                for tc_delta in tc_deltas:
                    idx = tc_delta.get("index", 0)
                    if idx not in tool_calls_by_index:
                        tool_calls_by_index[idx] = {"id": tc_delta.get("id", f"call_{idx}"), "type": "function", "function": {"name": "", "arguments": ""}}
                    tc = tool_calls_by_index[idx]
                    if tc_delta.get("id"): tc["id"] = tc_delta["id"]
                    fn_delta = tc_delta.get("function", {})
                    if fn_delta.get("name"): tc["function"]["name"] += fn_delta["name"]
                    if fn_delta.get("arguments"): tc["function"]["arguments"] += fn_delta["arguments"]

        except KeyboardInterrupt:
            if started_text:
                stream_md.abort()
            raise

        except LLMError as e:
            text = stream_md.abort() if started_text else ""
            print_error(str(e))
            return text, []
        except Exception as e:
            text = stream_md.abort() if started_text else ""
            print_error(str(e))
            return text, []

        full_text = ""
        if started_text:
            full_text = stream_md.finish()

        tool_calls = [tool_calls_by_index[i] for i in sorted(tool_calls_by_index)]
        return full_text, tool_calls

    def _complete_response(self) -> tuple[str, list[dict]]:
        data = self.llm.chat(self.state.messages, tools=self.state.tool_schemas)
        msg = data["choices"][0]["message"]
        text = msg.get("content") or ""
        raw_tcs = msg.get("tool_calls") or []
        tool_calls: list[dict] = []
        for tc in raw_tcs:
            fn = tc.get("function") or {}
            tool_calls.append({
                "id": tc.get("id", ""),
                "type": "function",
                "function": {"name": fn.get("name", ""), "arguments": fn.get("arguments", "") or ""},
            })
        return text, tool_calls

    # --- Extracted sub-methods from chat_turn ---

    def _ensure_context_budget(self) -> bool:
        """Check context window, compact if needed. Returns False if exhausted."""
        threshold = _context_low_threshold()
        remaining = self.state.context_remaining(self.llm.last_usage)
        if remaining < threshold:
            console.print(warning("  context nearly full, compacting..."))
            self.state.auto_compact(self.llm.chat, self.llm.last_usage)
            if self.state.context_remaining(self.llm.last_usage) < threshold:
                print_error("Context exhausted. Use /clear to reset.")
                return False
        return True

    def _validate_tool_calls(self, tool_calls: list[dict]) -> tuple[list[dict], list[tuple]]:
        """Separate valid and malformed tool calls."""
        valid_tcs, malformed = [], []
        for tc in tool_calls:
            raw_args = tc.get("function", {}).get("arguments", "")
            try:
                if isinstance(raw_args, str) and raw_args.strip():
                    json.loads(raw_args)
                valid_tcs.append(tc)
            except json.JSONDecodeError as e:
                malformed.append((tc, e))
        return valid_tcs, malformed

    def _handle_malformed(self, malformed: list[tuple]) -> None:
        """Report malformed tool calls and add retry guidance to context."""
        for tc, e in malformed:
            fn_name = tc.get("function", {}).get("name", "unknown")
            raw_args = tc.get("function", {}).get("arguments", "")
            print_tool_call(fn_name, {"_raw": raw_args[:100]})
            error_msg = json.dumps({"error": f"Malformed JSON in tool arguments: {e}"})
            print_tool_result(error_msg, success=False)
            self.state.messages.append({
                "role": "user",
                "content": f"You attempted to call the tool '{fn_name}', but the JSON arguments were malformed. Error: {e}\nPlease retry with perfectly formatted JSON."
            })

    def _check_tool_limit(self, count: int) -> bool:
        """Returns True if the tool call limit has been exceeded."""
        if count > self.max_iterations:
            console.print(warning(f"  tool call limit reached ({self.max_iterations})"))
            self.state.messages.append({
                "role": "system",
                "content": f"[CIRCUIT BREAKER: Maximum tool call limit ({self.max_iterations}) reached. You must stop and provide your final answer or ask for help.]"
            })
            return True
        return False

    def _check_circuit_breaker(self, valid_tcs: list[dict]) -> bool:
        """Track tool calls and trip breaker if same call repeated 3x. Returns True if tripped."""
        for tc in valid_tcs:
            fn = tc.get("function", {})
            tool_name = fn.get("name", "")
            raw_args = fn.get("arguments", "")
            try:
                args_obj = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                file_target = None
                range_key = ""
                if isinstance(args_obj, dict):
                    for key in _FILE_TARGET_KEYS:
                        if key in args_obj:
                            file_target = str(args_obj[key])
                            break
                    range_parts = []
                    for rk in _RANGE_KEYS:
                        if rk in args_obj:
                            range_parts.append(f"{rk}={args_obj[rk]}")
                    range_key = "|".join(range_parts)
            except (json.JSONDecodeError, TypeError):
                file_target = None
                range_key = ""

            if file_target is not None:
                tool_sig = (tool_name, file_target, range_key)
                self._tool_history.append(tool_sig)

                if len(self._tool_history) >= 3:
                    if self._tool_history[-1] == self._tool_history[-2] == self._tool_history[-3]:
                        console.print(warning(f"  circuit breaker: '{tool_name}' called on same file 3x in a row"))
                        self.state.messages.append({
                            "role": "system",
                            "content": f"[CIRCUIT BREAKER: You have called '{tool_name}' on the same file ({file_target}) with the same parameters 3 times in a row. Stop repeating this call. Proceed to the next step or provide your final answer.]"
                        })
                        # Add dummy responses for orphaned tool calls
                        for orphan in valid_tcs:
                            self.state.messages.append({
                                "role": "tool",
                                "tool_call_id": orphan["id"],
                                "content": '{"error": "Circuit breaker tripped — call skipped."}'
                            })
                        return True
        return False

    def _print_status(self) -> None:
        """Print token usage summary."""
        print_token_status(
            {
                "tokens_used": self.state.context_used(self.llm.last_usage),
                "context_window": self.state.context_window,
                "remaining": self.state.context_remaining(self.llm.last_usage),
                "messages": len(self.state.messages),
                "tokens_source": "api" if self.llm.last_usage else "estimate"
            },
            self.llm.last_usage
        )
    def _process_image_results(self, tool_results: list[dict]) -> list[dict]:
        """Intercept view_image tool results and inject multimodal user messages."""
        processed = []
        for result in tool_results:
            content = result.get("content", "")
            try:
                data = json.loads(content) if isinstance(content, str) else {}
            except (json.JSONDecodeError, TypeError):
                data = {}

            if data.get(IMAGE_MARKER):
                # Replace the tool result text with a confirmation
                image_path = data.get("path", "image")
                result["content"] = json.dumps({"status": f"Image '{image_path}' loaded and sent to model for analysis."})
                processed.append(result)
                # Inject a multimodal user message with the actual image
                processed.append({
                    "role": "user",
                    "content": data["content"],  # The multimodal content list
                })
                console.print(f"  [dim]📷 image injected: {image_path}[/dim]")
            else:
                processed.append(result)
        return processed

    # --- Main entry point ---

    def chat_turn(self, user_input: str | list):
        """Run one user turn: add message, loop LLM rounds until final answer."""
        self.state.messages.append({"role": "user", "content": user_input})
        self.state.tool_call_count = 0
        self._tool_history.clear()
        self.state.auto_compact(self.llm.chat, self.llm.last_usage)

        try:
            while True:
                if not self._ensure_context_budget():
                    return

                if self.stream: text, tool_calls = self._stream_response()
                else: text, tool_calls = self._complete_response()

                valid_tcs, malformed = self._validate_tool_calls(tool_calls)

                assistant_msg: dict = {"role": "assistant", "content": text or ""}
                if valid_tcs: assistant_msg["tool_calls"] = valid_tcs
                self.state.messages.append(assistant_msg)

                if malformed:
                    self._handle_malformed(malformed)

                if not valid_tcs and not malformed:
                    break

                if valid_tcs:
                    self.state.tool_call_count += len(valid_tcs)
                    if self._check_tool_limit(self.state.tool_call_count):
                        break
                    if self._check_circuit_breaker(valid_tcs):
                        break

                    tool_results = self.executor.run_tool_calls(valid_tcs)
                    tool_results = self._process_image_results(tool_results)
                    self.state.messages.extend(tool_results)
                    continue

            self._print_status()

        except KeyboardInterrupt:
            console.print(warning("\n  [Interrupted by user (Ctrl+C)]"))
            if self.state.messages and self.state.messages[-1]["role"] == "assistant" and self.state.messages[-1].get("tool_calls"):
                dummy = [{"role": "tool", "tool_call_id": tc["id"], "content": "{\"error\": \"Canceled by user interrupt.\"}"} for tc in self.state.messages[-1]["tool_calls"]]
                self.state.messages.extend(dummy)
            self.state.messages.append({"role": "system", "content": "[User interrupted the agent (Ctrl+C). Await next instruction.]"})
