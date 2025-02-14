from dataclasses import dataclass
from textual.widget import Widget
from textual.widgets import TextArea, Button, RichLog, Input
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding
from textual.message import Message
from textual.reactive import var
from textual import on, events, work
from textual_autocomplete import AutoComplete, Dropdown, DropdownItem
from textual.worker import Worker
import asyncio

from langchain.schema import BaseMessage

from ..widget.chatbox import Chatbox, ChatboxContainer
from ..widget.file_search import FileSearcher
from ..display.chat_header import ChatHeader
from ..display.typing_indicator import IsTyping

from pathlib import Path


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

    def __init__(self, chat: "Chat", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.chat = chat

    def _on_focus(self, event: events.Focus) -> None:
        super()._on_focus(event)
        self.chat.scroll_to_latest_message()

    def action_search(self):
        self.screen.action_search()


class Chat(Widget):
    CSS_PATH = "styling.tcss"

    def __init__(self, llm, graph, state):
        super().__init__()
        self.llm = llm
        self.graph = graph
        self.state = state
        self.chat_container: ScrollableContainer | None = None
        self.input_area = ChatInputArea(self, id="chat-input", classes="multiline")
        self.responding_indicator = IsTyping()
        self.responding_indicator.display = False
        self.chatboxes = {}
        self.multiline = True
        # Initialize debug output
        self.debug_log = None

    allow_input_submit = var(True)
    """Used to lock the chat input while the agent is responding."""

    def compose(self) -> ComposeResult:
        #yield ChatHeader()
        with Vertical(id="chat-input-container"):
            with Horizontal(id="chat-input-text-container"):
                yield self.input_area
                yield Button("Send", id="btn-submit")
                yield self.responding_indicator
        scroll = VerticalScroll(
                id="chat-scroll-container",)
        self.chat_container = scroll # Get the VerticalScroll widget
        yield scroll

    def on_mount(self) -> None:
        # Ensure textual-autocomplete layer exists
        screen_layers = list(self.screen.styles.layers)
        if "selection-list" not in screen_layers:
            screen_layers.append("selection-list")
        self.screen.styles.layers = tuple(screen_layers)

    @on(TextArea.Changed)
    async def on_input_changed(self, event: TextArea.Changed):
        if not self.input_area:
            return

        # Get current content height
        current_height = len(self.input_area.text.split('\n'))
        current_is_multiline = current_height > 1

        if current_is_multiline != self.multiline:
            self.multiline = current_is_multiline
            self.input_area.remove_class("singleline")
            self.input_area.remove_class("multiline")
            self.input_area.add_class("multiline" if current_is_multiline else "singleline")
            self.refresh(layout=True)


        cursor = self.input_area.cursor_location
        if cursor is None:
            return
        current_line = self.input_area.document.get_line(cursor[0])
        if str("/file") in current_line and cursor[1] - (current_line.index("/file")+5) == 1:
            selection_list = FileSearcher(text_area=self.input_area, search="file")
            assert self.chat_container
            #await self.chat_container.mount(selection_list)
            selection_list.focus()

        if str("/dir") in current_line and cursor[1] - (current_line.index("/dir")+4) == 1:
            selection_list = FileSearcher(text_area=self.input_area, search="dirs")
            assert self.chat_container
            p = Path('/')
            autocomplete = AutoComplete(
                input=Input(placeholder="Type to search..."),
                dropdown=Dropdown(items=[DropdownItem(str(file)) for file in p.iterdir()])
            )
            #await self.chat_container.mount(selection_list)
            await self.chat_container.mount(autocomplete)
            selection_list.focus()


    @on(ChatInputArea.Submit)
    async def user_chat_message_submitted(self, event: ChatInputArea.Submit) -> None:
        if self.allow_input_submit:
            user_message = event.input_area.text
            if len(user_message):
                event.input_area.clear()
                await self.chat(user_message)

    @on(Button.Pressed, selector='#btn-submit')
    def on_submit(self, event: Button.Pressed):
        event.stop()
        self.input_area.post_message(ChatInputArea.Submit(self.input_area))
        self._debug_widget_tree(self, 0)

    @dataclass
    class MessageSubmitted(Message):
        chat_id: str

    @dataclass
    class AIResponseReceived(Message):
        chat_id: str
        message: BaseMessage

    async def mount_message(self, chatbox: Chatbox):
        # Create container with proper styling
        if self.debug_log:
            self.debug_log.write("mounting message\n")
        container = ChatboxContainer()
        assert self.chat_container
        await self.chat_container.mount(container)
        await container.mount(chatbox)
        self.scroll_to_latest_message()

    def scroll_to_latest_message(self):
        if self.chat_container is not None:
            # Calculate scroll position accounting for input area height
            input_height = self.query_one("#chat-input-container").outer_size.height
            self.chat_container.scroll_to(
                y=self.chat_container.virtual_size.height - input_height,
                animate=False
            )


    async def chat(self, content: str):
        try:
            # Create user message box
            if self.debug_log:
                self.debug_log.write("Creating user message\n")
            user_box = Chatbox(content)
            assert self.chat_container is not None
            await self.mount_chat_boxes([user_box])

            # Show typing indicator
            self.responding_indicator.display = True
            # Update state with user input
            self.state["messages"] = self.state["messages"] + [{
                "role": "user",
                "content": content
            }]
            self.state["current_input"] = content
            self.state["should_end"] = False

            # Process through graph
            if self.debug_log:
                self.debug_log.write("Processing through graph\n")
            ai_box = Chatbox("", is_ai=True)

            try:
                # Try direct process_input first
                #processed_state = self.graph.process_input(self.state)
                #if self.debug_log:
                #    self.debug_log.write(f"Processed state: {processed_state}\n")
                await self.mount_chat_boxes([ai_box])
                #processed_state = self.graph.stream_process_input(self.state, ai_box)
                async def stream_response():
                    response = []
                    async for chunk in self.llm.astream(self.state["current_input"]):
                        response.append(chunk.content)
                        ai_box.update_content(response)
                        self.scroll_to_latest_message()

                self.run_worker(stream_response)
                '''
                if processed_state and "action_output" in processed_state:
                    ai_box.content = str(processed_state["action_output"])
                    ai_box.refresh()
                    self.scroll_to_latest_message()
                    await self.mount_chat_boxes([ai_box])
                '''


            except Exception as e:
                if self.debug_log:
                    self.debug_log.write(f"Error in process_input: {str(e)}\n")
            #self.state = self.graph.invoke(self.state)

            if self.debug_log:
                self.debug_log.write(f"{self.state['messages']}\n")
            ai_box.refresh()
            self.scroll_to_latest_message()
            self.responding_indicator.display = False

        except Exception as e:
            if self.debug_log:
                self.debug_log.write(f"Error in chat: {str(e)}\n")
                import traceback
                self.debug_log.write(traceback.format_exc())


    async def mount_chat_boxes(self, boxes: list[Chatbox]):
        if self.debug_log:
            self.debug_log.write(f"Mounting {len(boxes)} messages\n")
        assert self.chat_container

        for box in boxes:
            # Create a simple container with the content
            container = ChatboxContainer()


            # Mount the container directly
            await self.chat_container.mount(container)
            await container.mount(box)


            # Force refresh
            self.chat_container.refresh(layout=True)

        # Final refresh and scroll
        self.chat_container.refresh(layout=True)
        self.chat_container.scroll_end(animate=False)

    def _debug_widget_tree(self, widget, depth):
        if self.debug_log is None:
            return
        indent = "  " * depth
        self.debug_log.write(f"{indent}{widget}\n")
        for child in widget.children:
            self._debug_widget_tree(child, depth + 1)
