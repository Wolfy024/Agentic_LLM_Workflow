"""
Extra prompt_toolkit key bindings for the MINILLM REPL.

When the slash-command completion menu is open, Enter applies the selected
completion instead of submitting the line (same idea as many shells/IDEs).
"""

from __future__ import annotations

from prompt_toolkit.application import get_app
from prompt_toolkit.filters import Condition
from prompt_toolkit.key_binding import KeyBindings


@Condition
def _slash_completion_menu_open() -> bool:
    try:
        b = get_app().current_buffer
    except Exception:
        return False
    st = b.complete_state
    if st is None or not st.completions:
        return False
    return b.document.text.lstrip().startswith("/")


def build_repl_key_bindings() -> KeyBindings:
    kb = KeyBindings()

    # eager=True: win over default "accept line" when both match (same key).
    @kb.add("enter", filter=_slash_completion_menu_open, eager=True)
    def _enter_apply_slash_completion(event) -> None:
        b = event.current_buffer
        st = b.complete_state
        assert st is not None
        c = st.current_completion if st.complete_index is not None else st.completions[0]
        b.apply_completion(c)

    return kb
