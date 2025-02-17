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
        self.index_path = "./conversations/index.json"
        self.conversation_path = "./conversations"
        self.current_chat_id = ""
        self.is_new_chat = True
        self.index = self._load_index()
        self.options = self._load_conversations()

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
                        "Chat History",
                    )
                )
                option_list = OptionList(
                    *[Option(data["chat_name"], id=conv_id) for conv_id, data in self.options.items()],
                    id="cl-option-list",
                )
                yield option_list

           # with Horizontal(id="cl-button-container"):
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

    def on_option_list_option_selected(self, event: OptionList.OptionSelected) -> None:
        conversation_id = event.option.id
        self.current_chat_id = conversation_id
        print("HELLO BAKA")
        print(conversation_id)
        if conversation_id in self.index:
            self.current_chat_id = conversation_id
            # Post a message that will be handled by the Chat widget
            self.post_message(self.ChatOpened(conversation_id))

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

    # REDO THIS METHOD THIS IS SHIT
    def delete_conversation(self, conversation_id: str) -> bool:
        index = None
        if Path(self.index_path).exists():
            with open(self.index_path, 'r') as f:
                index = json.load(f)
        if conversation_id not in self.index:
            return False

        file_path = Path(self.index[conversation_id]["path"])
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
        try:
            conv_id = uuid()
            if not name:
                name = str(datetime.now())
            index = None
            if Path(self.index_path).exists():
                with open(self.index_path, 'r') as f:
                    index = json.load(f)
                f.close()
            else:
                index = {}
            conv_file_path = Path(self.conversation_path) / f"{conv_id}.json"
            path = Path(self.conversation_path + f"/{conv_id}.json")
            index[conv_id] = {"path": str(path), "chat_name": name, "timestamp": str(datetime.now())} #ConversationIndex(str(path), str(name), str(datetime.now()))
            new_conversation = {
                "id": conv_id,
                "name": name,
                "timestamp": str(datetime.now()),
                "messages": []  # Initialize empty messages list
            }
            # Write the new conversation file
            with open(conv_file_path, 'w') as f:
                json.dump(new_conversation, f, indent=4)
            with open(self.index_path, 'w') as f:
                json.dump(index, f, indent=4)
            self.index = index
            self.refresh()
            self.current_chat_id = conv_id
            return True
        except Exception:
            return False

    def update_conversation_single(self, conversation_id: str, message: MessageClass) -> bool:
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return False
        file_path = conversation_index["path"]
        with open(file_path, 'r') as f:
            jsoned = json.load(f)
            f.close()
        jsoned["messages"].append({"_from": message._from, "content": message.content, "timestamp": message.timestamp})
        with open(file_path, 'w') as fr:
            json.dump(jsoned, fr, indent=4)
            fr.close()
        return True

    def update_conversation_multiple(self, conversation_id: str, messages: List[MessageClass]) -> bool:
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return False
        file_path = conversation_index["path"]
        with open(file_path, 'r') as f:
            jsoned = json.load(f)
            f.close()
        jsoned["messages"] = [{"_from": message._from, "content": message.content, "timestamp": message.timestamp} for message in messages]
        with open(file_path, 'w') as fr:
            json.dump(jsoned, fr, indent=4)
            fr.close()
        return True

    def load_conversation(self, conversation_id: str):
        conversation_index = self.index[conversation_id]
        if not conversation_index: return {}
        file_path = Path(conversation_index["path"])
        try:
            with open(file_path, 'r') as f:
                contents = json.load(f)
                return [MessageClass(**msg) for msg in contents["messages"]]
        except Exception as e:
            print('conversation not found')
            return []
