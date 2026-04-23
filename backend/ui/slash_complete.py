"""
Slash-command completion for the prompt_toolkit REPL.

Shows a completion menu (dropdown) when the line starts with `/` — type `/`
or `/h` and use Tab or keep typing to filter.
"""

from __future__ import annotations

from prompt_toolkit.completion import Completer, Completion

# Same behavior as repl.slash.execute_slash_command exit aliases.
_SLASH_ALIASES: tuple[tuple[str, str], ...] = (
    ("/quit", "Quit"),
    ("/q", "Quit (short)"),
)


class SlashCommandCompleter(Completer):
    def __init__(self, specs: list[tuple[str, str]]):
        self._rows = list(specs) + list(_SLASH_ALIASES)

    def get_completions(self, document, complete_event):
        # Use text_before_cursor only — works across prompt_toolkit versions
        # (cursor_position_in_line is not always present on Document).
        line = document.text_before_cursor.split("\n")[-1]

        fs = line.find("/")
        if fs < 0:
            return
        prefix = line[fs:]
        if " " in prefix:
            return

        for cmd, desc in self._rows:
            if cmd.startswith(prefix):
                yield Completion(cmd, start_position=-len(prefix), display_meta=desc)
