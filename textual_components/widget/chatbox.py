from __future__ import annotations

import re
from langchain.schema import BaseMessage, AIMessage

import pyperclip

from rich.console import RenderableType
from rich.markdown import Markdown
from textual.binding import Binding
from textual.geometry import Size
from textual.widget import Widget
from textual.containers import Container
from rich.text import Text
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
        self.content = content if content else "Empty Message"
        self.is_ai = is_ai

    @property
    def is_ai_message(self) -> bool:
        return self.is_ai

    def on_mount(self) -> None:
        if self.is_ai:
            self.add_class("assistant-message")
        self.update(self.content)

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
        return Markdown(self.content or "PLACEHOLDER")

    def render(self) -> RenderableType:
        return self.markdown


    def get_content_height(self, container, viewport, width) -> int:
            lines = self.content.split('\n')
            return max(3, len(lines))  # At least 3 lines high

    def get_content_width(self, container, viewport) -> int:
        return container.width if container else 80  # Default width if no container
