"""
Agent main event loop.

Orchestrates the synchronous completion rounds, streaming generation, 
and tool evaluation chains for the LLM interactive shell.
"""

from __future__ import annotations
import json
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


class AgentRunner:
    def __init__(self, state: SessionState, llm: LLMClient, executor: ToolExecutor, stream: bool = True):
        self.state = state
        self.llm = llm
        self.executor = executor
        self.stream = stream
        self.max_iterations = 25

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
            if started_text: stream_md.abort()
            print_error(str(e))
            return stream_md.abort() if started_text else "", []
        except Exception as e:
            if started_text: stream_md.abort()
            print_error(str(e))
            return stream_md.abort() if started_text else "", []

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

    def chat_turn(self, user_input: str | list):
        self.state.messages.append({"role": "user", "content": user_input})
        self.state.tool_call_count = 0
        self.state.auto_compact(self.llm.chat, self.llm.last_usage)

        try:
            while True:
                remaining = self.state.context_remaining(self.llm.last_usage)
                if remaining < 2000:
                    console.print(warning("  context nearly full, compacting..."))
                    self.state.auto_compact(self.llm.chat, self.llm.last_usage)
                    if self.state.context_remaining(self.llm.last_usage) < 2000:
                        print_error("Context exhausted. Use /clear to reset.")
                        return

                if self.stream: text, tool_calls = self._stream_response()
                else: text, tool_calls = self._complete_response()

                valid_tcs = []
                malformed_errors = []
                if tool_calls:
                    for tc in tool_calls:
                        raw_args = tc.get("function", {}).get("arguments", "")
                        try:
                            if isinstance(raw_args, str) and raw_args.strip():
                                json.loads(raw_args)
                            valid_tcs.append(tc)
                        except json.JSONDecodeError as e:
                            malformed_errors.append((tc, e))

                assistant_msg: dict = {"role": "assistant", "content": text or ""}
                if valid_tcs: assistant_msg["tool_calls"] = valid_tcs
                self.state.messages.append(assistant_msg)

                if malformed_errors:
                    for tc, e in malformed_errors:
                        fn_name = tc.get("function", {}).get("name", "unknown")
                        raw_args = tc.get("function", {}).get("arguments", "")
                        print_tool_call(fn_name, {"_raw": raw_args[:100]})
                        error_msg = json.dumps({"error": f"Malformed JSON in tool arguments: {e}"})
                        print_tool_result(error_msg, success=False)
                        self.state.messages.append({
                            "role": "user",
                            "content": f"You attempted to call the tool '{fn_name}', but the JSON arguments were malformed. Error: {e}\nPlease retry with perfectly formatted JSON."
                        })

                if not valid_tcs and not malformed_errors:
                    break

                if valid_tcs:
                    self.state.tool_call_count += len(valid_tcs)
                    if self.state.tool_call_count > self.max_iterations:
                        console.print(warning("  tool call limit reached"))
                        break
                    
                    tool_results = self.executor.run_tool_calls(valid_tcs)
                    self.state.messages.extend(tool_results)

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

        except KeyboardInterrupt:
            console.print(warning("\n  [Interrupted by user (Ctrl+C)]"))
            if self.state.messages and self.state.messages[-1]["role"] == "assistant" and self.state.messages[-1].get("tool_calls"):
                dummy = [{"role": "tool", "tool_call_id": tc["id"], "content": "{\"error\": \"Canceled by user interrupt.\"}"} for tc in self.state.messages[-1]["tool_calls"]]
                self.state.messages.extend(dummy)
            self.state.messages.append({"role": "system", "content": "[User interrupted the agent (Ctrl+C). Await next instruction.]"})
