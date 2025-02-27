from textual.widget import Widget
from textual.widgets import TextArea, Button, Input, OptionList, ContentSwitcher, Static, Label, ListView, ListItem, Header
from textual.widgets.option_list import Option
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding
from textual.message import Message
from textual.reactive import var, reactive
from textual import on, events, work
from textual.events import Key
from textual.worker import Worker, WorkerState


from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import SecretStr

from textual_components.architect.input_area import ChatInputArea

import os

class AssistantPanel(Widget):
    DEFAULT_CSS = """
        AssistantPanel {
            layout: vertical;
            height: 100%;
        }

        #assistant-header {
            height: auto;
            margin-bottom: 1;
        }

        #assistant-messages {
            height: 1fr;  /* Take available space */
            margin-bottom: 1;
        }

        #files-loaded {
            height: auto;  /* Automatically size based on content */
            max-height: 10%;  /* But don't take more than 30% of the panel */
            border-top: solid $panel;
            padding: 1;
            overflow-y: scroll;
        }

        #files-loaded-header {
            height: auto;
            margin-bottom: 1;
            color: $text-muted;
        }

        #files-list {
            height: auto;  /* Automatically size based on content */
            margin-bottom: 1;
        }

        #assistant-input {
            height: auto;
            dock: bottom;
            margin-top: 1;
        }
        """
    loaded_files = reactive([])
    def __init__(self):
        super().__init__()
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)


    def compose(self):
        with Container(id="assistant-header"):
            yield Label("AI ASSISTANT", id="assistant-title")

        with ScrollableContainer(id="assistant-messages"):
            yield Static("I can help you with coding tasks. Ask me anything!")
        #yield Input(placeholder="Ask a question...", id="assistant-input")
        with Container(id="files-loaded"):
            yield Static(content="Files in the LLM context")
            with ScrollableContainer():
                self.list_view = ListView()
                yield self.list_view
        yield ChatInputArea(id="assistant-input")

    def add_file_to_loaded_files(self, file_data):
        #self.loaded_files = [*self.loaded_files, {"name": file_data.name, "path": file_data.path}]
        self.list_view.append(ListItem(Label(file_data["name"])))
        self.loaded_files.append({"name": file_data["name"], "path": file_data["path"]})

    def remove_file_from_loaded_files(self, file_data):
        index = self.loaded_files.index({"name": file_data["name"], "path": file_data["path"]})
        self.list_view.pop(index)
