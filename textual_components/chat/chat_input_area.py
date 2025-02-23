from textual.widgets import TextArea
from textual.binding import Binding
from textual.message import Message
from textual import on, events
from textual.css.query import NoMatches
from textual.events import Key
#from textual_autocomplete import AutoComplete, Dropdown, DropdownItem, InputState

from ..commands.file_search import SlashCommandPopup

from typing import List
import os
from functools import lru_cache
from dataclasses import dataclass

@dataclass
class InputState:
    value: str
    cursor_position: int

class ChatInputArea(TextArea):
    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="focus('cl-option-list')",
            description="Focus List",
            key_display="^s",
        ),
        Binding(
            key="ctrl+f",
            action="search",
            description="Search",
            key_display="^f",
        ),
    ]

    class Submit(Message):
        def __init__(self, textarea: "ChatInputArea") -> None:
            super().__init__()
            self.input_area = textarea

        @property
        def control(self):
            return self.input_area

    def __init__(self, chat, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat = chat
        self.current_command = None

    def _on_focus(self, event: events.Focus) -> None:
        super()._on_focus(event)
        self.chat.scroll_to_latest_message()

    def reset_height(self):
        self.styles.height = "auto"


    @on(TextArea.Changed)
    async def on_input_changed(self, event: TextArea.Changed):
        cursor = self.cursor_location
        if cursor is None:
            return

        current_line = self.document.get_line(cursor[0])
        # Only show for /file command and when there's a space after it
        if str("@file") in current_line and cursor[1] - (current_line.index("@file")+5) == 1:
            # Remove any existing popup
            existing = self.query("SlashCommandPopup")
            for widget in existing:
                widget.remove()

            # Create new popup
            popup = SlashCommandPopup(self)
            self.styles.height="25"
            await self.mount(popup)
        else:
            self.reset_height()

    @on(Key)
    def on_key(self, event: Key) -> None:
        try:
            if self.query_one("SlashCommandPopup") and event.key == "enter":
                popup = self.query_one("SlashCommandPopup")
                popup.confirm_selection()
                self.action_cursor_down()
                event.prevent_default()
        except NoMatches:
            pass
    #def action_search(self):
        #self.screen.action_search()
