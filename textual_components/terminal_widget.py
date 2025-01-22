from textual.widget import Widget
from textual.containers import ScrollableContainer
from textual.reactive import reactive
from textual.message import Message
from textual import events
import asyncio
from typing import Optional
from cli.child_terminal import ChildTerminal
from cli.listener import Listener
from cli.process_monitor import ProcessMonitor
from cli.terminal_wrapper import TerminalWrapper

class TerminalWidget(Widget):
    """A Textual widget that wraps the ChildTerminal functionality"""

    terminal_output = reactive("")
    current_input: str

    class TerminalOutput(Message):
        """Message sent when terminal output changes"""
        def __init__(self, output: str) -> None:
            self.output = output
            super().__init__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        #self.terminal = ChildTerminal(port=port)
        #self.monitor = ProcessMonitor(self.terminal)
        #self.listener = Listener(port=port)
        self.terminal_session = TerminalWrapper(port=None)
        self.current_input = ""

    def on_mount(self) -> None:
        """Called when widget is mounted"""
        self.terminal_session.terminal.open_new_terminal()
        #self.terminal_session.monitor.start_monitoring()
        #self.terminal_session.listener.start()
        # Start monitoring output
        self.set_interval(0.1, self._check_output)

    def on_unmount(self) -> None:
        """Called when widget is unmounted"""
        self.terminal_session.terminal.kill_tmux_session()
        self.terminal_session.listener.stop()

    async def _check_output(self) -> None:
        """Check terminal output periodically"""
        output = self.terminal_session.terminal.read_tmux_output()
        if output:
            if output.get('stdout'):
                self.terminal_output = output['stdout']
            if output.get('stderr'):
                self.terminal_output = output['stderr']
            self.post_message(self.TerminalOutput(self.terminal_output))

    def execute_command(self, command: str) -> None:
        """Execute a command in the terminal"""
        self.terminal_session.terminal.send_to_terminal(command)

    def render(self) -> str:
        """Render the terminal output"""
        return self.terminal_output
    async def on_key(self, event: events.Key) -> None:
        """Handle keyboard input"""
        if event.key == "enter":
            # Handle enter key
            self.execute_command(self.current_input)
            self.current_input = ""
        else:
            # Append character to current input
            self.current_input += event.character
