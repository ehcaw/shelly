from datetime import datetime
from dataclasses import dataclass
from typing import Dict, Literal, List, Optional

from rich.text import Text
from textual.app import ComposeResult
from textual.message import Message
from textual.binding import Binding
from textual.reactive import var
from textual.widget import Widget
from textual.widgets import Button, OptionList, Static
from textual.widgets.option_list import Option
from textual.containers import Vertical


from pathlib import Path
from shortuuid import uuid
import json
import os
from functools import lru_cache

from .footer import CommandFooter, Command, Field

@dataclass
class ConversationIndex:
    path: str
    name: str
    timestamp: str

    def __getitem__(self, key):
        return getattr(self, key)

@dataclass
class MessageClass:
    _from: Literal["user", "ai"]
    content: str
    timestamp: str
    summary: Optional[str]

    def __getitem__(self, key):
        return getattr(self, key)


class ChatHistory(Widget):
    BINDINGS = [
        Binding("r", "rename_conversation", "Rename Chat", key_display="r"),
        Binding("d", "delete_conversation", "Delete Chat", key_display="d")
    ]

    current_chat_id: var[str | None] = var(None)
    index: Dict[str, ConversationIndex]

    def __init__(self, app):
        super().__init__()
        self.app_dir = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self._app = app
        self.index_path = self.app_dir / "conversations/index.json"
        self.conversation_path = self.app_dir / "conversations"
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
                self.option_list = OptionList(
                    *[Option(data["chat_name"] if len(data["chat_name"]) < 40 else data["chat_name"][:40 ] + "...", id=conv_id) for conv_id, data in self.options.items()],
                    id="cl-option-list",
                )
                yield self.option_list

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
        print("HELLO BAKA")
        print(conversation_id)
        if conversation_id in self.index:
            # Post a message that will be handled by the Chat widget
            self.post_message(self.ChatOpened(conversation_id))

    def action_delete_conversation(self):
        if self.current_chat_id:
            footer: CommandFooter = self.app.query_one(CommandFooter)
            print("Footer found:", footer)  # Debug print

            if footer.command:
                print("Existing command found, returning")  # Debug print

            fields = (Field("yes/no", bool),)
            footer.command = Command("Delete this Chat?", fields, self.delete_conversation(self.current_chat_id))
            print("Command set:", footer.command)  # Debug print

            self.screen.set_focus(footer)
            print("Focus set to footer")  # Debug print
            self.options = self._load_conversations()

            self.option_list.clear_options()
            # Add new options
            for conv_id, data in self.options.items():
                display_name = data["chat_name"] if len(data["chat_name"]) < 40 else data["chat_name"][:40] + "..."
                self.option_list.add_option(Option(display_name, id=conv_id))
            self._app.chat_container.remove_children()
            self.refresh(layout=True)

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
        assert index
        del index[conversation_id]
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
            relative_path = f"conversations/{conv_id}.json"
            conv_file_path = self.app_dir / relative_path
            index[conv_id] = {"path": relative_path, "chat_name": name, "timestamp": str(datetime.now())}
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

    def add_conversation_single(self, conversation_id: str, message: MessageClass, summary: str) -> bool:
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return False
        file_path = self.app_dir / conversation_index["path"]
        with open(file_path, 'r') as f:
            conversation = json.load(f)
        message_dict = {
            "_from": message._from,
            "content": message.content,
            "timestamp": message.timestamp,
            "summary": summary
        }
        conversation["messages"].append(message_dict)
        with open(file_path, 'w') as fr:
            json.dump(conversation, fr, indent=4)
        return True

    def update_conversation_single(self, conversation_id: str, message: MessageClass, summary: str) -> bool:
        try:
            conversation_index = self.index[conversation_id]
            if not conversation_index:
                return False

            file_path = conversation_index["path"]

            # First read the entire file
            with open(file_path, 'r') as f:
                conversation = json.load(f)

            # Update the summary
            if conversation["messages"]:  # Check if there are messages
                conversation["messages"][-1]["summary"] = summary

            # Write the entire updated conversation back to file
            with open(file_path, 'w') as f:
                json.dump(conversation, f, indent=4)

            return True

        except Exception as e:
            print(f"Error updating conversation: {e}")
            import traceback
            print(traceback.format_exc())
            return False

    def update_conversation_multiple(self, conversation_id: str, messages: List[MessageClass]) -> bool:
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return False
        file_path = conversation_index["path"]
        with open(file_path, 'r') as f:
            jsoned = json.load(f)
            f.close()
        jsoned["messages"] = [{"_from": message._from, "content": message.content, "timestamp": message.timestamp, "summary": message.summary} for message in messages]
        with open(file_path, 'w') as fr:
            json.dump(jsoned, fr, indent=4)
            fr.close()
        return True

    @lru_cache
    def load_conversation(self, conversation_id: str):
        conversation_index = self.index[conversation_id]
        self.current_chat_id = conversation_id
        if not conversation_index: return {}
        file_path = self.app_dir / conversation_index["path"]
        try:
            with open(file_path, 'r') as f:
                contents = json.load(f)
                return [MessageClass(**msg) for msg in contents["messages"]]
        except Exception as e:
            print('conversation not found')
            return []

    def get_conversation_name(self, conversation_id: str):
        conversation_index = self.index[conversation_id]
        if not conversation_index:
            return "Untitled chat"
        file_path = Path(str(self.app_dir) + "/" + conversation_index["path"])
        try:
            with open(file_path, 'r') as f:
                contents = json.load(f)
                print(contents)
                return contents["name"]
        except Exception as e:
            print('conversation not found')
            return "Untitled chat"
