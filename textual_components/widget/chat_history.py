from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Literal, List

from rich.console import Console
from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.binding import Binding
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option, Separator
from pathlib import Path
from shortuuid import uuid

import json

from .footer import CommandFooter, Command, Field

@dataclass
class ConversationIndex:
    path: str
    name: str
    timestamp: str

@dataclass
class MessageClass:
    _from: Literal["user", "ai"]
    content: str
    timestamp: str


class ChatHistory(Widget):
    BINDINGS = [
        Binding("r", "rename_conversation", "Rename Chat", key_display="r"),
        Binding("d", "delete_conversation", "Delete Chat", key_display="d")
    ]

    current_chat_id: var[str | None] = var(None)
    index: Dict[str, ConversationIndex]

    def __init__(self):
        super().__init__()
        self.index_path = "conversations/index.json"
        self.conversation_path = "conversations"
        self.current_chat_id = ""
        self.index = self._load_index()

    @dataclass
    class ChatOpened(Message):
        chat_id: str
    @dataclass
    class ChatDeleted(Message):
        chat_id: str

    def compose(self) -> ComposeResult:
            with Vertical(id="cl-header-container"):
                yield Static(
                    Text(
                    )
                )
                yield Static(
                    Text(
                        "LLMs in the Terminal",
                    )
                )

            self.options = self._load_conversations()
            option_list = OptionList(
                *self.options,
                id="cl-option-list",
            )
            yield option_list

            with Horizontal(id="cl-button-container"):
                yield Button("New Chat", id="cl-new-chat-button")

    def _load_conversations(self):
        if Path(self.index_path).exists():
            with open(self.index_path, 'r') as f:
                return json.load(f)
        return {}

    def _load_index(self):
        if Path(self.index_path).exists():
            with open(self.index_path, 'r') as f:
                index = json.load(f)
            f.close()
            return index
        index = dict()
        return index

    def action_delete_conversation(self):
        if self.current_chat_id:
            footer: CommandFooter = self.app.query_one(CommandFooter)
            if footer.command:
                return

            def delete_chat(values):
                confirm: bool = values[0]
                if confirm:

                    self.current_chat_id = None
                self.query_one(OptionList).focus()

            fields = (Field("yes/no", bool),)
            footer.command = Command("Delete this Chat?", fields, delete_chat)
            self.screen.set_focus(footer)

    def delete_conversation(self, conversation_id: str) -> bool:
        index = None
        if Path(self.index_path).exists():
            with open(self.index_path, 'r') as f:
                index = json.load(f)
        if conversation_id not in self.index:
            return False

        file_path = Path(self.index[conversation_id].path)
        try:
            file_path.unlink()
        except FileNotFoundError:
            pass
        del self.index[conversation_id]
        with open(self.index_path, 'w') as f:
            json.dump(index, f, indent=4)

        return True



    # REDO THIS METHOD THIS IS SHIT
    def rename_conversation(self, conversation_id: str, new_name: str) -> bool:
        index = None
        if Path(self.index_path).exists():
            with open(self.index_path, 'r') as f:
                index = json.load(f)
            f.close()
        if not index or conversation_id not in index:
            return False
        file_path = Path(index[conversation_id]["path"])
        file_path.rename(new_name)
        return True

    def add_conversation(self, name: str | None) -> bool:
        conv_id = uuid()
        if not name:
            name = str(datetime.now())
        index = None
        if Path(self.index_path).exists():
            with open(self.index_path, 'r') as f:
                index = json.load(f)
            f.close()
        if not index:
            return False
        path = Path(self.conversation_path + f"/{conv_id}")
        index["conversations"].append(ConversationIndex(str(path), str(name), str(datetime.now())))
        return True

    def update_conversation_single(self, conversation_id: str, message: MessageClass) -> bool:
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return False
        file_path = conversation_index.path
        with open(file_path, 'r') as f:
            jsoned = json.load(f)
            f.close()
        jsoned.messages.append(message)
        with open(file_path, 'w') as fr:
            json.dump(jsoned, fr, indent=4)
            fr.close()
        return True

    def update_conversation_multiple(self, conversation_id: str, messages: List[MessageClass]) -> bool:
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return False
        file_path = conversation_index.path
        with open(file_path, 'r') as f:
            jsoned = json.load(f)
            f.close()
        jsoned.messages = messages
        with open(file_path, 'w') as fr:
            json.dump(jsoned, fr, indent=4)
            fr.close()
        return True
