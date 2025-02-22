from __future__ import annotations
import os

from textual.reactive import reactive
from textual.app import ComposeResult
from textual.widget import Widget
from textual.widgets import Static, Select, Button, Input
from textual.css.query import NoMatches
from textual.containers import Horizontal
from textual.message import Message
from dataclasses import dataclass

from langchain_groq import ChatGroq
from pydantic import SecretStr

class ChatHeader(Widget):
    """A header widget for the chat interface with model selection."""
    DEFAULT_CSS = """
        ChatHeader {
            height: 3;
            padding: 0;  /* Removed padding */
            background: $surface;
            border-bottom: solid $primary;
        }

        #header-container {
            align: left middle;
            height: 3;  /* Match parent height */
            padding: 0 1;
        }

        #title-container {
            width: 60%;
            height: 3;  /* Match parent height */
        }

        #model-container {
            width: 40%;
            height: 3;  /* Match parent height */
        }

        #title-static {
            color: $text;
            text-style: bold;
            height: 3;  /* Match parent height */
            content-align: left middle;  /* Vertically center text */
        }

        #title-input {
            display: none;
            height: 3;  /* Match parent height */
        }

        #title-input.editing {
            display: block;
        }

        #title-static.editing {
            display: none;
        }

        Select {
            width: 100%;
            height: 3;  /* Match parent height */
        }

        Button {
            height: 3;  /* Match parent height */
            min-width: 3;
        }
        """

    title = reactive("Untitled Chat", init=False)
    model_name = reactive("", init=False)
    is_editing = reactive(False, init=False)

    # Available models
    MODELS = [
        ("llama-3.3-70b-versatile", "Llama 70B Versatile"),
        ("llama3-8b-8192", "Llama  8B"),
        ("qwen-2.5-32b", "Qwen 2.5 32b"),
        ("deepseek-r1-distill-qwen-32b", "Deepseek R1 Distill Qwen 32b")
        # Add more models as needed
    ]

    def __init__(self, chat):
        super().__init__()
        self._title = "Untitled Chat"
        self._model_name = ""
        self._is_editing = False
        self.parent_chat = chat



    # Custom messages
    @dataclass
    class TitleChanged(Message):
        """Sent when the chat title is changed."""
        new_title: str

    @dataclass
    class ModelChanged(Message):
        """Sent when the model is changed."""
        model_id: str
        model_name: str

    def compose(self) -> ComposeResult:
        """Compose the header widget."""
        with Horizontal(id="header-container"):
            # Title section
            with Horizontal(id="title-container"):
                yield Static(self.title, id="title-static")
                yield Input(
                    value=self.title,
                    id="title-input",
                    placeholder="Enter chat title"
                )
                yield Button("✎", id="edit-title")

            # Model selector section
            with Horizontal(id="model-container"):
                initial_model = self._model_name if self._model_name else self.MODELS[0][1]
                yield Select(
                    options=self.MODELS,  # Properly format options
                    value=initial_model,
                    id="model-select",
                    allow_blank=False
                )

    def on_mount(self) -> None:
        """Handle widget mount."""
        self.title = self._title
        self.model_name = self._model_name
        self.is_editing = self._is_editing

    def watch_is_editing(self, is_editing: bool) -> None:
        """Watch for editing state changes."""
        try:
            title_static = self.query_one("#title-static", Static)
            title_input = self.query_one("#title-input", Input)

            if is_editing:
                title_static.add_class("editing")
                title_input.remove_class("editing")
                title_input.focus()
            else:
                title_static.remove_class("editing")
                title_input.add_class("editing")
        except NoMatches:
            # Widget not mounted yet
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "edit-title":
            self.is_editing = not self.is_editing
            self.update_title_display()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle input submission."""
        if event.input.id == "title-input":
            self.title = event.value
            self.is_editing = False
            self.update_title_display()
            self.post_message(self.TitleChanged(event.value))

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle model selection changes."""
        selected_value = event.value
        assert selected_value
        # Find the model ID and name based on the selected display name
        if selected_value and selected_value != Select.BLANK:
            model_id = next(id for id, name in self.MODELS if name == selected_value)
            self.model_name = model_id
            api_key = os.getenv('GROQ_API_KEY')
            if not api_key:
                raise ValueError("GROQ_API_KEY environment variable is not set")
            # Initialize the LLM
            self.parent_chat.llm = ChatGroq(
                    model=model_id,
                    api_key= SecretStr(api_key),
                    temperature=0,
                    stop_sequences=None)
            self.post_message(self.ModelChanged(model_id, str(selected_value)))

    def update_title_display(self) -> None:
        """Update the visibility of title components."""
        title_static = self.query_one("#title-static", Static)
        title_input = self.query_one("#title-input", Input)

        if self.is_editing:
            title_static.add_class("editing")
            title_input.remove_class("editing")
            title_input.focus()
        else:
            title_static.remove_class("editing")
            title_input.add_class("editing")

    def watch_title(self, new_title: str) -> None:
        """Watch for title changes."""
        title_static = self.query_one("#title-static", Static)
        title_input = self.query_one("#title-input", Input)
        title_static.update(new_title)
        title_input.value = new_title
        title_static.refresh(layout=True)
        title_input.refresh(layout=True)
