"""
Tool dispatch logic and concurrent execution.

Decodes LLM function calls, validates them against user safety profiles and
approval limits, and runs them.
"""

from __future__ import annotations
import json
import difflib
import threading
from concurrent.futures import ThreadPoolExecutor

from ui.tool_logs import (
    print_tool_call,
    print_tool_result,
    print_permission_approved,
    print_permission_denied,
)
from tools.registry import execute_tool
from core.permissions_checks import is_tool_denied_in_profile, is_destructive
from core.permissions_prompts import ask_edit_confirmation, ask_permission
from tools.fs.edit import preview_replace_in_file, preview_patch_file

_PARALLEL_SAFE_TOOLS = {
    "read_file", "search_files", "find_files", "list_directory", "file_info",
    "git_status", "git_log", "git_diff", "git_search", "git_blame", "git_show",
    "read_url", "web_search", "web_search_news", "web_search_images",
    "github_api", "summarize_code", "count_tokens_estimate"
}


class ToolExecutor:
    def __init__(self, confirm_edits: bool, verbose: bool):
        self.confirm_edits = confirm_edits
        self.verbose = verbose
        self._tool_io_lock = threading.Lock()

    def parallel_batch_ok(self, tool_calls: list[dict]) -> bool:
        if len(tool_calls) < 2:
            return False
        for tc in tool_calls:
            fn = tc["function"]
            name = fn["name"]
            raw_args = fn.get("arguments", "")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except json.JSONDecodeError:
                return False
            if name not in _PARALLEL_SAFE_TOOLS:
                return False
            if name == "github_api" and args.get("method", "GET").upper() != "GET":
                return False
            if self.confirm_edits and name in ("replace_in_file", "patch_file"):
                return False
            if is_tool_denied_in_profile(name, args):
                continue
            if is_destructive(name, args):
                return False
        return True

    def dispatch_one_tool_call(self, tc: dict) -> dict:
        fn = tc["function"]
        name = fn["name"]
        raw_args = fn.get("arguments", "")

        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
        except json.JSONDecodeError as e:
            with self._tool_io_lock:
                print_tool_call(name, {"_raw": raw_args[:100]})
                error_msg = json.dumps({
                    "error": f"Malformed JSON in tool arguments: {e}. Raw: {raw_args[:200]}..."
                })
                print_tool_result(error_msg, success=False)
            return {"role": "tool", "tool_call_id": tc["id"], "content": error_msg}

        with self._tool_io_lock:
            print_tool_call(name, args)

        if is_tool_denied_in_profile(name, args):
            err = json.dumps({"error": f"Tool '{name}' is blocked in profile."})
            with self._tool_io_lock: print_tool_result(err, success=False)
            return {"role": "tool", "tool_call_id": tc["id"], "content": err}

        if self.confirm_edits and name == "replace_in_file":
            ok, before, after = preview_replace_in_file(args.get("path", ""), args.get("old_string", ""), args.get("new_string", ""), args.get("replace_all", False))
            if not ok:
                err = json.dumps({"error": before})
                with self._tool_io_lock: print_tool_result(err, success=False)
                return {"role": "tool", "tool_call_id": tc["id"], "content": err}
            diff = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=args.get("path","before"), tofile=args.get("path","after"), lineterm=""))
            if not ask_edit_confirmation(args.get("path", ""), diff or "(no textual change)"):
                with self._tool_io_lock: print_permission_denied()
                err = json.dumps({"error": "User rejected edit preview (replace_in_file)."})
                with self._tool_io_lock: print_tool_result(err, success=False)
                return {"role": "tool", "tool_call_id": tc["id"], "content": err}
                
        if self.confirm_edits and name == "patch_file":
            ok, before, after = preview_patch_file(args.get("path", ""), args.get("edits") or [])
            if not ok:
                err = json.dumps({"error": before})
                with self._tool_io_lock: print_tool_result(err, success=False)
                return {"role": "tool", "tool_call_id": tc["id"], "content": err}
            diff = "\n".join(difflib.unified_diff(before.splitlines(), after.splitlines(), fromfile=args.get("path","before"), tofile=args.get("path","after"), lineterm=""))
            if not ask_edit_confirmation(args.get("path", ""), diff or "(no textual change)"):
                with self._tool_io_lock: print_permission_denied()
                err = json.dumps({"error": "User rejected edit preview (patch_file)."})
                with self._tool_io_lock: print_tool_result(err, success=False)
                return {"role": "tool", "tool_call_id": tc["id"], "content": err}

        # Never hold _tool_io_lock during prompt() or execute_tool — nested prompt_toolkit / long I/O can hang.
        result: str
        if is_destructive(name, args):
            if not ask_permission(name, args):
                with self._tool_io_lock:
                    print_permission_denied()
                result = json.dumps({"error": "Permission denied by user."})
            else:
                with self._tool_io_lock:
                    print_permission_approved()
                result = execute_tool(name, args)
        else:
            result = execute_tool(name, args)

        is_error = result.startswith('{"error"') or result.startswith("[exit")
        with self._tool_io_lock:
            print_tool_result(result, success=not is_error, verbose=self.verbose)

        return {"role": "tool", "tool_call_id": tc["id"], "content": result}

    def run_tool_calls(self, tool_calls: list[dict]) -> list[dict]:
        if self.parallel_batch_ok(tool_calls):
            max_w = min(8, len(tool_calls))
            with ThreadPoolExecutor(max_workers=max_w) as ex:
                try:
                    return list(ex.map(self.dispatch_one_tool_call, tool_calls))
                except KeyboardInterrupt:
                    ex.shutdown(wait=False, cancel_futures=True)
                    raise
        return [self.dispatch_one_tool_call(tc) for tc in tool_calls]
