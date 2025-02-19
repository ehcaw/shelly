from __future__ import annotations

import re
import pyperclip

from rich.console import RenderableType
from rich.markdown import Markdown
from textual.binding import Binding
from textual.containers import Container
from textual.widgets import Static

class ChatboxContainer(Container):
    ...

class Chatbox(Static, can_focus=True):  # Change Widget to Static
    BINDINGS = [
        Binding(
            key="ctrl+s",
            action="focus('cl-option-list')",
            description="Focus List",
            key_display="^s",
        ),
        Binding(
            key="i",
            action="focus('chat-input')",
            description="Focus Input",
            key_display="i",
        ),
        Binding(
            key="d", action="details", description="Message details", key_display="d"
        ),
        Binding(key="c", action="copy", description="Copy Message", key_display="c"),
        Binding(key="`", action="copy_code", description="Copy Code Blocks"),
    ]

    def __init__(self, content: str, is_ai: bool = False):
        super().__init__(content)  # Pass content to Static
        self.is_ai = is_ai
        self.content = content
        self.styles.height = "auto"
        self.styles.min_height = "1"
        self.styles.width = "100%"
        self.styles.box_sizing = "border-box"
        self.styles.padding = (1, 2, 2, 2)
        self.styles.overflow_y="scroll"
        self.styles.visibility = "visible"
        self.current_length = len(content)
        self.update_content(content)
        self.prefix_added = False
        self.is_streaming = False

    @property
    def is_ai_message(self) -> bool:
        return self.is_ai


    def on_mount(self) -> None:
        if self.is_ai:
            self.add_class("assistant-message")
        self.styles.height = "auto"
        self.styles.width = 'auto'
        self.refresh(layout=True)

    def get_code_blocks(self, markdown_string):
        pattern = r"```(.*?)\n(.*?)```"
        code_blocks = re.findall(pattern, markdown_string, re.DOTALL)
        return code_blocks

    def action_copy_code(self):
        codeblocks = self.get_code_blocks(self.content)
        output = ""
        if codeblocks:
            for lang, code in codeblocks:
                output += f"{code}\n\n"
            pyperclip.copy(output)
            self.notify("Codeblocks have been copied to clipboard", timeout=3)
        else:
            self.notify("There are no codeblocks in the message to copy", timeout=3)

    def action_copy(self) -> None:
        pyperclip.copy(self.content)
        self.notify("Message content has been copied to clipboard", timeout=3)

    @property
    def markdown(self) -> Markdown:
        print(self.content)
        return Markdown(self.content)

    def render(self) -> RenderableType:
        return self.markdown

    def get_content_height(self, container, viewport, width) -> int:
        lines = str(self.content).split('\n')
        # Add extra lines for padding
        return len(lines) + 2

    def get_content_width(self, container, viewport) -> int:
        return container.width  # Default width if no container

    def update_content(self, content):
        new_content = "".join(content)
        self.content = new_content
        self.current_length = len(new_content)
        self.refresh(layout=True)
