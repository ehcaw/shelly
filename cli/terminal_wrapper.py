from .child_terminal import ChildTerminal
from .listener import Listener
from .process_monitor import ProcessMonitor

class TerminalWrapper:
    child_terminal: ChildTerminal
    listener: Listener
    monitor: ProcessMonitor
    def __init__(self):
        self.terminal = ChildTerminal(port=5555)
        self.monitor = ProcessMonitor(self.terminal)
        self.listener = Listener(port=5555)

        self.monitor.start_monitoring()
        self.listener.start()

    def execute_in_terminal(self, command):
        # Send commands to the terminal
        return self.terminal.send_to_terminal(command)

    def open_terminal(self):
        # Open a new terminal window
        return self.terminal.open_new_terminal()

    def cleanup(self):
        # Cleanup when closing
        self.terminal.kill_tmux_session()
        self.listener.stop()
