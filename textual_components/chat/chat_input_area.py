from textual.widget import Widget
from textual.widgets import TextArea, RichLog, Input, OptionList
from textual.containers import ScrollableContainer, Vertical, VerticalScroll
from textual.binding import Binding
from textual.message import Message
from textual import on, events
from textual.css.query import NoMatches
from textual.events import Key
#from textual_autocomplete import AutoComplete, Dropdown, DropdownItem, InputState

from textual_components.commands.file_search import SlashCommandPopup

from typing import List
import os
from dataclasses import dataclass
from functools import lru_cache

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


    @on(TextArea.Changed)
    async def on_input_changed(self, event: TextArea.Changed):
        cursor = self.cursor_location
        if cursor is None:
            return

        if len(self.text.split('\n')) + 3 >= self.parent.size.height:
            self.parent.styles.height = "1fr"
        else:
            self.parent.styles.height = "auto"

        current_line = self.document.get_line(cursor[0])
        # Only show for /file command and when there's a space after it
        await self.handle_command(current_line)

    @on(Key)
    def on_key(self, event: Key) -> None:
        try:
            if event.key in ("ctrl+enter", "shift+enter"):
                self.post_message(ChatInputArea.Submit(self))
                return
            if self.query_one("SlashCommandPopup") and event.key == "enter":
                popup = self.query_one("SlashCommandPopup")
                popup.confirm_selection()
                event.prevent_default()
                self.styles.height = "auto"
                return
        except NoMatches:
            pass

    async def handle_command(self, current_line):
        cursor = self.cursor_location
        if cursor is None: return
        current_line = self.document.get_line(cursor[0])
        if (current_line.startswith("@file") and cursor[1] - (current_line.index("@file")+5) == 1) or (current_line.startswith(":f") and cursor[1] - (current_line.index(":f")+2) == 1):
            # Remove any existing popup
            existing = self.query("SlashCommandPopup")
            for widget in existing:
                widget.remove()

            # Create new popup
            popup = SlashCommandPopup(self, get_directories=False)
            self.styles.height = "25"
            await self.mount(popup)
        if (current_line.startswith("@dir") and cursor[1] - (current_line.index("@dir")+4) == 1) or (current_line.startswith(":d") and cursor[1] - (current_line.index(":d")+2) == 1):
            # Remove any existing popup
            existing = self.query("SlashCommandPopup")
            for widget in existing:
                widget.remove()

            # Create new popup
            popup = SlashCommandPopup(self, get_directories=True)
            self.styles.height = "25"
            await self.mount(popup)

    @lru_cache
    def _get_files(self, max_files: int = 100) -> List[str]:
        """Get filtered list of files from current directory"""
        ignore_patterns = {
            # Directories to ignore
            '.git', '__pycache__', 'node_modules', 'venv', '.env',
            # File patterns to ignore
            '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll',
            '*.exe', '*.bin', '*.obj', '*.cache',
            # Add more patterns as needed
        }

        files = []
        cwd = os.getcwd()

        for root, dirs, filenames in os.walk(cwd, topdown=True):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]

            for filename in filenames:
                # Skip ignored file patterns
                if any(filename.endswith(pat.replace('*', '')) for pat in ignore_patterns):
                    continue

                rel_path = os.path.relpath(os.path.join(root, filename), cwd)
                files.append(rel_path)

                if len(files) >= max_files:
                    return sorted(files)

        return sorted(files)
    #def action_search(self):
        #self.screen.action_search()

class ScrollableChatContainer(ScrollableContainer):
    DEFAULT_CSS = """
        ScrollableChatContainer {
            height: auto;        /* Allow natural expansion */
            max-height: 200;     /* But cap it at a specific height */
            overflow-y: auto;    /* Enable scrolling when content exceeds max-height */
        }

        TextArea {
            width: 100%;
            height: auto;
        }
        """
    def __init__(self, input_area):
        super().__init__()
        self.input_area = input_area

    def compose(self):
        yield self.input_area
