from textual.app import App
from langchain_groq import ChatGroq
from pydantic import SecretStr
import os
import asyncio
from dotenv import load_dotenv
from textual.widgets import RichLog, Header
from textual.containers import Vertical, Grid, ScrollableContainer
from textual_components.terminal_widget import PtyTerminal, TabbedTerminals
from textual.message import Message
from textual.widgets import Static
from dataclasses import dataclass
from typing import Callable
from functools import wraps
import time

from textual_components.chat.chat import Chat


load_dotenv()

def debounce(wait):
    def decorator(fn):
        last_call = 0
        @wraps(fn)
        def debounced(*args, **kwargs):
            nonlocal last_call
            current_time = time.time()
            if current_time - last_call >= wait:
                last_call = current_time
                return fn(*args, **kwargs)
        return debounced
    return decorator

class Shelly(App):
    CSS_PATH = "textual_components/styling.tcss"
    CSS = """
    Grid#main_grid {
        grid-size: 2;  /* 2 columns */
        grid-columns: 3fr 1fr;  /* 75% - 25% split */
        height: 100%;
        margin: 1;
    }
     #left_panel {
        height: 100%;
        width: 100%;
    }
    """
    BINDINGS = [
        ("m", "maximise", "Maximise the focused widget"),
        ("ctrl+t", "new_terminal", "New Terminal"),
        ("ctrl+w", "close_terminal", "Close Terminal"),
        ("super+r", "refresh_screen", "Refresh Screen")
    ]
    def __init__(self):
        super().__init__()
        self.child_terminal = None
        #self.zapper = SimpleChat()
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.versatile_llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)
        self.simple_llm = ChatGroq(
            model="llama3-8b-8192",
            api_key=SecretStr(api_key),
            temperature=0,
            stop_sequences=None
        )
        self.zapper = Zapper(self.simple_llm)
        # token usage plot intialization
        self.operation_counter = 0
        self.operations = []
        self.total_token_usage = 0
        self.token_usage = []

    @property
    def state(self):
        if self.zapper is None:
            return None
        return self.zapper.state

    @state.setter
    def state(self, value):
        if self.zapper is not None:
            self.zapper.state = value

    def compose(self):
        """Create ui loadout"""
        yield Header(id="header", name="Shelly", show_clock=True)

        with Grid(id="main_grid"):
            # Left side - Chat component
            with Vertical(id="left_panel"):
                yield Chat(
                    app=self
                )

            # Right side - Your existing components
            with Vertical(id="right_panel"):
                #yield TokenUsagePlot(id="token_usage")
                yield RichLog(id="debug_log")
                with ScrollableContainer(id="terminal_panel"):
                    yield TabbedTerminals()

    '''
    def action_new_terminal(self):
        """Add a new terminal tab."""
        terminal_tabs = self.query_one(TabbedTerminals)
        terminal_tabs.add_terminal()

    def action_close_terminal(self):
        """Close the current terminal tab."""
        terminal_tabs = self.query_one(TabbedTerminals)
        terminal_tabs.action_close_terminal()
    '''

    def action_maximise(self):
        """Maximise the focused widget"""
        focused_widget = self.focused
        assert focused_widget
        self.screen.maximize(focused_widget)

    def action_refresh_screen(self):
        self.refresh(layout=True)


    async def on_shutdown(self) -> None:
        """Clean up when the application is shutting down"""
        # Add any cleanup code here
        if self.child_terminal:
            self.child_terminal.kill_tmux_session()

    async def on_mount(self) -> None:
        """Called after the app is mounted"""
        await asyncio.sleep(1)  # Wait for widgets to be ready
        debug_log = self.query_one("#debug_log", RichLog)
        chat = self.query_one(Chat)
        assert chat.debug_log
        chat.debug_log = debug_log


@dataclass
class Command:
    """Represents a command that can be triggered"""
    name: str
    description: str
    handler: Callable
    args: list = None

class Alert(Message):
    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__()

class AlertWidget(Static):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def main():
    """Entry point for the command-line interface"""
    try:
        shelly = Shelly()
        shelly.run()
    except Exception as e:
        print(f"Error: {e}")
        return 1
    return 0

if __name__ == "__main__":
    main()
