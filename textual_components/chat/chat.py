from textual.widget import Widget
from textual.widgets import TextArea, Button, Input, OptionList, ContentSwitcher, Static
from textual.widgets.option_list import Option
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding
from textual.message import Message
from textual.reactive import var
from textual import on, events, work
from textual.events import Key
from textual.worker import Worker, WorkerState


from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.prompts import ChatPromptTemplate

from ..widget.chatbox import Chatbox, ChatboxContainer
from ..commands.file_search import SlashCommandPopup
from ..widget.chat_header import ChatHeader
from ..widget.typing_indicator import IsTyping
from ..widget.chat_history import ChatHistory, MessageClass
from ..widget.vertical_tabs import VerticalContentSwitcher
from ..commands.file_search import SlashCommandPopup
from ..commands.autocomplete import AutoComplete, Dropdown, DropdownItem
from ..chat.chat_input_area import ChatInputArea, ScrollableChatContainer

from pathlib import Path
from datetime import datetime
from dataclasses import dataclass
from typing import List
import os
import asyncio
from functools import lru_cache



class Chat(Widget):
    CSS_PATH = "styling.tcss"

    def __init__(self, app):
        super().__init__()
        self._app = app
        self.chat_container: ScrollableContainer | None = None
        self.input_area = ChatInputArea(self, id="chat-input", classes="multiline")
        self.responding_indicator = IsTyping()
        self.responding_indicator.display = False
        self.chatboxes = {}
        self.multiline = True
        # Initialize debug output
        self.debug_log = None
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI assistant. Provide clear and concise responses for the user's requests. Use a combination of your own knowledge and the context, with more emphasis on using the context."),
            ("user", "{input}"),
            ("user", "Here are previous messages you should use for context: {context}"),
        ])


    allow_input_submit = var(True)
    """Used to lock the chat input while the agent is responding."""

    @property
    def llm(self):
        return self._app.versatile_llm
    @llm.setter
    def llm(self, value):
        self._app_versatile_llm = value

    @property
    def context(self):
        return self._app.zapper.state["summaries"]

    @property
    def graph(self):
        return self._app.zapper
    @graph.setter
    def graph(self, value):
        self._app.zapper = value

    @property
    def state(self):
        return self._app.zapper.state
    @state.setter
    def state(self, value):
        self._app.zapper.state = value

    @property
    def current_chat_id(self):
        if self.chat_history is None:
            return None
        return self.chat_history.current_chat_id
    @current_chat_id.setter
    def current_chat_id(self, value):
        if self.chat_history is not None:
            self.chat_history.current_chat_id = value

    @property
    def is_new_chat(self):
        if self.chat_history is None:
            return None
        return self.chat_history.is_new_chat
    @is_new_chat.setter
    def is_new_chat(self, value):
        if self.chat_history is not None:
            self.chat_history.is_new_chat = value

    '''
    def compose(self) -> ComposeResult:
        with Horizontal(id="chat-app"):
            # Left sidebar
            with Vertical(id="sidebar"):
                self.vertical_tabs = VerticalContentSwitcher(self)
                yield self.vertical_tabs
            with Vertical(id="chathistory"):
                self.chat_header = ChatHeader(self)
                yield self.chat_header
                chat_history = ChatHistory(self)
                self.chat_history = chat_history
                yield chat_history
            # Main chat area
            with Vertical(id="main-chat-area"):
                # Chat messages scroll area
                with Vertical(id="chat-input-container"):
                    with Horizontal(id="chat-input-text-container"):
                        self.scrollable_container = ScrollableChatContainer(self.input_area)
                        yield self.scrollable_container
                        yield Button("Send", id="btn-submit")
                        yield self.responding_indicator
                scroll = VerticalScroll(id="chat-scroll-container")
                self.chat_container = scroll
                yield scroll

    def on_mount(self) -> None:
        # Ensure textual-autocomplete layer exists
        screen_layers = list(self.screen.styles.layers)
        if "selection-list" not in screen_layers:
            screen_layers.append("selection-list")
        self.screen.styles.layers = tuple(screen_layers)
    '''
    def compose(self) -> ComposeResult:
        with Horizontal(id="chat-app"):
            # Left sidebar
            with Vertical(id="sidebar"):
                self.vertical_tabs = VerticalContentSwitcher(self)
                yield self.vertical_tabs

            # Create main content area with both views
            self.main_content = ContentSwitcher()
            with self.main_content:
                # Chat view
                with Container(id="chat-view") as chat_view:
                    with Horizontal():
                        with Vertical(id="chathistory"):
                            self.chat_header = ChatHeader(self)
                            yield self.chat_header
                            self.chat_history = ChatHistory(self)
                            yield self.chat_history

                        with Vertical(id="main-chat-area"):
                            with Vertical(id="chat-input-container"):
                                with Horizontal(id="chat-input-text-container"):
                                    self.scrollable_container = ScrollableChatContainer(self.input_area)
                                    yield self.scrollable_container
                                    yield Button("Send", id="btn-submit")
                                    yield self.responding_indicator
                            scroll = VerticalScroll(id="chat-scroll-container")
                            self.chat_container = scroll
                            yield scroll
                self.chat_view = chat_view

                # Architect view
                with Container(id="architect-view") as architect_view:
                    yield Static("Architect View")
                self.architect_view = architect_view
            self.main_content.add_content(chat_view, set_current=True)
            self.main_content.add_content(architect_view, set_current=False)
            yield self.main_content

    def on_mount(self) -> None:
        # Set initial screen
        self.main_content.current = "chat-view"

        # Ensure textual-autocomplete layer exists
        screen_layers = list(self.screen.styles.layers)
        if "selection-list" not in screen_layers:
            screen_layers.append("selection-list")
        self.screen.styles.layers = tuple(screen_layers)


    # Then in your tab change handler
    def on_vertical_content_switcher_tab_changed(self, message: VerticalContentSwitcher.TabChanged):
        self.debug_log.write(message.tab_id)
        self.debug_log.write(self.chat_view.id)
        self.debug_log.write(self.architect_view.id)
        if message.tab_id == "chat":
            self.main_content.current = "chat-view"
        elif message.tab_id == "architect":
            self.main_content.current = "architect-view"


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

    @on(ChatHistory.ChatOpened)
    async def on_chat_opened(self, message: ChatHistory.ChatOpened) -> None:
        if self.chat_history.current_chat_id and message.chat_id == self.chat_history.current_chat_id:
            return
        if self.chat_container:
            self.chat_container.remove_children()
        self.chat_history.current_chat_id = message.chat_id
        messages = self.chat_history.load_conversation(message.chat_id)
        self.debug_log.write(messages)
        self.chat_header.watch_title(self.chat_history.get_conversation_name(message.chat_id))
        chatboxes = []
        for msg in messages:
            chatbox = Chatbox(msg.content, is_ai=(msg._from == "ai"))
            chatboxes.append(chatbox)
        await self.mount_chat_boxes(chatboxes)
        self.is_new_chat = False

    @on(Button.Pressed, selector="#cl-new-chat-button")
    def on_new_chat(self) -> None:
        """Handle new chat button press."""
        # Clear current chat container
        if self.chat_container:
            self.chat_container.remove_children()

        # Create new conversation
        self.is_new_chat = True
        # Refresh the option list
        option_list = self.query_one("#cl-option-list", OptionList)
        option_list.clear_options()
        options = self.chat_history._load_conversations()
        option_list.add_options([Option(data["chat_name"] if len(data["chat_name"]) < 40 else data["chat_name"][:40] + "...", id=conv_id) for conv_id, data in options.items()])

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
            total_content_height = self.chat_container.virtual_size.height
            visible_height = self.chat_container.size.height

            # Calculate maximum scroll position
            max_scroll = max(0, total_content_height - visible_height)

            # Force scroll to bottom
            self.chat_container.scroll_to(y=max_scroll, animate=False)
            self.chat_container.refresh(layout=True)

    def process_content(self, content: str) -> str:
        # Split content into lines first
        lines = content.splitlines()
        i = 0
        assert self.debug_log

        while i < len(lines):
            line = lines[i]
            split_line = line.split()
            self.debug_log.write(split_line)

            if len(split_line) == 2:
                if line.startswith(":f ") or line.startswith("@file"):  # File command
                    try:
                        file_path = Path(split_line[1])
                        if file_path.is_file():
                            file_contents = file_path.read_text(encoding='utf-8')
                            lines[i] = f"# File: {file_path}\n{file_contents}"
                            i += len(file_contents.splitlines()) + 1  # +1 for the header
                        else:
                            lines[i] = f"# Error: File not found - {file_path}"
                    except Exception as e:
                        lines[i] = f"# Error reading file: {str(e)}"

                elif line.startswith(":d ") or line.startswith("@dir"):  # Directory command
                    try:
                        dir_path = Path(split_line[1])
                        if dir_path.is_dir():
                            dir_contents = []
                            dir_contents.append(f"# Directory contents of: {dir_path}")
                            for file_path in dir_path.rglob('*'):
                                if (file_path.is_file() and
                                    not any(ignore in str(file_path) for ignore in ['.git', '__pycache__', 'node_modules']) and
                                    file_path.suffix.lower() in ['.py', '.js', '.jsx', '.ts', '.tsx', '.java', '.cpp', '.h', '.rs', '.go']):
                                    try:
                                        file_contents = file_path.read_text(encoding='utf-8')
                                        dir_contents.append(f"\n# File: {file_path.relative_to(dir_path)}\n{file_contents}")
                                    except (UnicodeDecodeError, PermissionError):
                                        continue
                            if len(dir_contents) > 1:  # If we found any files
                                lines[i] = '\n'.join(dir_contents)
                                i += len(dir_contents)
                            else:
                                lines[i] = f"# No readable source files found in directory: {dir_path}"
                        else:
                            lines[i] = f"# Error: Directory not found - {dir_path}"
                    except Exception as e:
                        lines[i] = f"# Error reading directory: {str(e)}"
            i += 1

        # Join the lines back into a single string
        processed_content = '\n'.join(lines)
        self.debug_log.write(processed_content)
        return processed_content

    async def chat(self, content: str):
        try:
            # Create user message box
            if self.debug_log:
                self.debug_log.write("Creating user message\n")
            #Check if this is a new chat and create one
            if self.is_new_chat:
                self.chat_history.add_conversation(content)
                self.is_new_chat = False
                #self.chat_history.refresh(layout=True)
                option_list = self.chat_history.query_one(OptionList)
                option_list.clear_options()
                updated_options = self.chat_history._load_conversations()
                option_list.add_options([Option(data["chat_name"] if len(data["chat_name"]) < 40 else data["chat_name"][:40] + "...", id=conv_id) for conv_id, data in updated_options.items()])

            user_box = Chatbox(content)
            assert self.chat_container is not None
            await self.mount_chat_boxes([user_box])

            user_message = MessageClass(
                _from="user",
                content=content,
                timestamp = str(datetime.now()),
                summary = content
            )
            if self.chat_history.current_chat_id:
                self.chat_history.add_conversation_single(self.chat_history.current_chat_id, user_message, content)

            # Show typing indicator
            self.responding_indicator.display = True
            # Update state with user input
            self.state["messages"] = self.state["messages"] + [{
                "role": "user",
                "content": content
            }]
            self._app.zapper.add_user_input_to_summaries(content)

            self.state["current_input"] = content
            self.state["should_end"] = False

            # Process through graph
            if self.debug_log:
                self.debug_log.write("Processing through graph\n")
            try:
                ai_box = Chatbox("", is_ai=True)
                await self.mount_chat_boxes([ai_box])
                response = []
                async def stream_response():
                    assert self.chat_container
                    prompt = self.prompt.format_messages(input=self.state["current_input"], context=self.context)
                    async for chunk in self.llm.astream(prompt):
                        response.append(chunk.content)
                        ai_box.update_content(response)
                        await asyncio.sleep(0.01)
                        ai_box.refresh(layout=True)
                        self.chat_container.refresh(layout=True)
                        self.scroll_to_latest_message()
                    await asyncio.sleep(0.05)  # Slightly longer delay for final update
                    ai_box.refresh(layout=True)
                    self.chat_container.refresh(layout=True)
                    self.scroll_to_latest_message()
                    return "".join(response)
                self.run_worker(stream_response)

            except Exception as e:
                if self.debug_log:
                    self.debug_log.write(f"Error in process_input: {str(e)}\n")
            #self.state = self.graph.invoke(self.state)

            if self.debug_log:
                self.debug_log.write(f"{self.state['messages']}\n")
            self.scroll_to_latest_message()
            self.responding_indicator.display = False

        except Exception as e:
            if self.debug_log:
                self.debug_log.write(f"Error in chat: {str(e)}\n")
                import traceback
                self.debug_log.write(traceback.format_exc())

    async def on_worker_state_changed(self, event: Worker.StateChanged) -> None:
        if event.worker.state == WorkerState.SUCCESS and event.worker.result:
            response = event.worker.result
            current_time = str(datetime.now())
            if self.chat_history.current_chat_id:
                ai_message = MessageClass(
                    _from="ai",
                    content=str(response),
                    timestamp=current_time,
                    summary="Generating summary"
                )
                self.chat_history.add_conversation_single(
                    self.chat_history.current_chat_id,
                    ai_message,
                    "Generating summary"
                )
                await self.summarize_and_update(str(response), ai_message)



    async def summarize_and_update(self, response: str, ai_message: MessageClass) -> None:
        try:
            await self._app.zapper.summarize_message(str(response))
            last_summary = self.context[-1]
            summary_content = last_summary.content if isinstance(last_summary, AIMessage) else str(last_summary)
            summary_content = str(summary_content)
            ai_message.summary = summary_content
            if self.chat_history.current_chat_id:
                self.chat_history.update_conversation_single(self.chat_history.current_chat_id, ai_message, summary_content if summary_content else "no summary found")

        except Exception as e:
            if self.debug_log:
                self.debug_log.write(f"Error in summarization: {str(e)}\n")

    async def mount_chat_boxes(self, boxes: list[Chatbox]):
        if self.debug_log:
            self.debug_log.write(f"Mounting {len(boxes)} messages\n")
        assert self.chat_container

        for box in boxes:
            # Create a simple container with the content
            container = ChatboxContainer()
            await self.chat_container.mount(container)
            await container.mount(box)

            container.refresh(layout=True)
            box.refresh(layout=True)
            self.chat_container.refresh(layout=True)

            await asyncio.sleep(0.01)
            self.scroll_to_latest_message()

        self.chat_container.refresh(layout=True)
        await asyncio.sleep(0.01)  # Small delay to ensure layout is updated
        self.scroll_to_latest_message()

    def _debug_widget_tree(self, widget, depth):
        if self.debug_log is None:
            return
        indent = "  " * depth
        self.debug_log.write(f"{indent}{widget}\n")
        for child in widget.children:
            self._debug_widget_tree(child, depth + 1)

    # Use this method to load a conversation into the current llm state
    def state_loader(self, messages):
        state_messages = []
        context_messages = []
        for message in messages:
            if message._from == "user" and message.summary:
                context_messages.append(HumanMessage(content=message.summary))
            else:
                context_messages.append(AIMessage(content=message.summary))
            state_messages.append({"role": "user" if message._from=="user" else "ai", "content": message.content})
        self.state["messages"] = state_messages
        self.state["context"] = context_messages
