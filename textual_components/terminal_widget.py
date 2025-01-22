from textual.widgets import Static
from textual.geometry import Size
from textual.scroll_view import ScrollView
from textual.strip import Strip
from textual.message import Message
import pyte
import pty
import os
import asyncio
import fcntl
import termios
import struct
import signal
from rich.text import Text
from rich.style import Style
from collections import deque

# Setup logging


class PtyTerminal(Static, can_focus=True):
    """Advanced PTY Terminal widget with scrolling and full terminal emulation"""

    BINDINGS = [
        ("ctrl+c", "copy", "Copy"),
        ("ctrl+v", "paste", "Paste"),
        ("ctrl+k", "clear", "Clear"),
        ("pageup", "page_up", "Page Up"),
        ("pagedown", "page_down", "Page Down"),
    ]

    DEFAULT_CSS = """
    PtyTerminal {
        background: $surface;
        color: $text;
        height: 100%;
        border: solid $accent;
        overflow-y: scroll;
        padding: 0 1;
    }
    PtyTerminal:focus {
        border: double $accent;
    }
    """

    SPECIAL_KEYS = {
        "up": "\x1b[A",
        "down": "\x1b[B",
        "right": "\x1b[C",
        "left": "\x1b[D",
        "home": "\x1b[H",
        "end": "\x1b[F",
        "delete": "\x1b[3~",
        "pageup": "\x1b[5~",
        "pagedown": "\x1b[6~",
        "tab": "\t",
        "shift+tab": "\x1b[Z",
        "f1": "\x1bOP",
        "f2": "\x1bOQ",
        "f3": "\x1bOR",
        "f4": "\x1bOS",
        "f5": "\x1b[15~",
        "f6": "\x1b[17~",
        "f7": "\x1b[18~",
        "f8": "\x1b[19~",
        "f9": "\x1b[20~",
        "f10": "\x1b[21~",
        "f11": "\x1b[23~",
        "f12": "\x1b[24~",
    }

    class Scrolled(Message):
        """Message sent when terminal is scrolled"""
        def __init__(self, position: int) -> None:
            self.position = position
            super().__init__()

    def __init__(
        self,
        shell="/bin/bash",
        scroll_buffer_size=10000,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.shell = shell
        self.scroll_buffer_size = scroll_buffer_size

        # Terminal state
        self.rows = 24
        self.cols = 80
        self.scroll_position = 0

        # History
        self.command_history = deque(maxlen=1000)
        self.history_index = 0
        self.current_input = ""

        # Setup pyte
        self._screen = pyte.Screen(self.cols, self.rows)
        self.stream = pyte.Stream(self._screen)

        # PTY state
        self.master_fd = None
        self.pid = None
        self.process = None
        self.read_task = None

        # Selection and clipboard
        self.selection_start = None
        self.selection_end = None
        self.selected_text = ""

    def on_mount(self):
        """Initialize terminal when mounted"""
        self.start_pty()
        self.focus()

    def start_pty(self):
        """Start the PTY process with proper configuration"""
        self.pid, self.master_fd = pty.fork()

        if self.pid == 0:  # Child process
            env = {
                "TERM": "xterm-256color",
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.path.expanduser("~"),
                "LANG": "en_US.UTF-8",
                "COLORTERM": "truecolor",
            }
            os.execvpe(self.shell, [self.shell], env)
        else:
            # Parent process
            self.process = os.fdopen(self.master_fd, "wb+", buffering=0)
            self.read_task = asyncio.create_task(self._read_output())
            self._resize_pty()

            # Ensure ECHO is enabled
            try:
                attrs = termios.tcgetattr(self.master_fd)
                # Uncomment the following line to disable echo
                # attrs[3] = attrs[3] & ~termios.ECHO  # Disable echo
                termios.tcsetattr(self.master_fd, termios.TCSANOW, attrs)
            except Exception as e:
                pass

    def _resize_pty(self):
        """Update PTY size and handle screen resizing"""
        try:
            size = struct.pack("HHHH", self.rows, self.cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, size)
            # Reset the screen to clear old content and adjust to new size
            self._screen.reset()
            # Inform the shell of the new window size
            self.stream.feed(f"\x1b[8;{self.rows};{self.cols}t")
        except Exception as e:
            pass

    async def _read_output(self):
        """Read and process PTY output with proper buffering"""
        loop = asyncio.get_event_loop()
        while True:
            try:
                data = await loop.run_in_executor(
                    None, self.process.read, 4096
                )
                if not data:
                    break

                # Process the output
                decoded = data.decode(errors='ignore')
                self.stream.feed(decoded)

                # Refresh display after processing new data
                self.refresh()

            except Exception as e:
                break

    def render(self):
        """Render the terminal using pyte's screen buffer."""
        lines = []
        for y in range(self._screen.lines):
            line = self._screen.display[y]
            rich_line = Text()
            for char in line:
                if hasattr(char, 'fg'):
                    # pyte >=0.9: char is a Cell object
                    style = Style(
                        color=char.fg if char.fg != "default" else None,
                        bgcolor=char.bg if char.bg != "default" else None,
                        bold=char.bold,
                        italic=char.italics,
                        reverse=char.reverse,
                        underline=char.underscore,
                        strike=char.strikethrough,
                    )
                    rich_line.append(char.data, style=style)
                elif isinstance(char, str):
                    # pyte <0.9: char is a string
                    rich_line.append(char)
                else:
                    # Unexpected type
                    rich_line.append(str(char))
            # Highlight the cursor position
            if y == self._screen.cursor.y:
                if self._screen.cursor.x < len(rich_line):
                    rich_line.stylize("reverse", self._screen.cursor.x, self._screen.cursor.x + 1)
            lines.append(rich_line)

        return "\n".join(str(line) for line in lines)

    async def on_key(self, event):
        """Enhanced keyboard input handling"""
        if not self.process:
            return

        event.stop()
        try:
            # Handle special key combinations
            if event.key == "enter":
                self._handle_enter()
            elif event.key == "backspace":
                self._handle_backspace()
            elif event.key in self.SPECIAL_KEYS:
                self.process.write(self.SPECIAL_KEYS[event.key].encode())
            elif event.key.startswith("ctrl+"):
                self._handle_ctrl_key(event.key)
            elif event.key.startswith("shift+"):
                if event.character:
                    self.process.write(event.character.encode())
            else:
                if event.character:
                    self.process.write(event.character.encode())

            # Update current input for history
            if event.character and not event.key.startswith("ctrl+"):
                self.current_input += event.character

        except Exception as e:
            pass

    def _handle_enter(self):
        """Handle enter key press with command history"""
        self.process.write(b"\n")
        if self.current_input.strip():
            self.command_history.append(self.current_input)
            self.current_input = ""
            self.history_index = len(self.command_history)

    def _handle_backspace(self):
        """Handle backspace with proper character deletion"""
        self.process.write(b"\x7f")
        if self.current_input:
            self.current_input = self.current_input[:-1]

    def _handle_ctrl_key(self, key: str):
        """Handle control key combinations"""
        char = key.split("+")[1]

        if char == "c":
            # Ctrl+C (SIGINT)
            self.process.write(b"\x03")
        elif char == "d":
            # Ctrl+D (EOF)
            self.process.write(b"\x04")
        elif char == "z":
            # Ctrl+Z (SIGTSTP)
            self.process.write(b"\x1a")
        elif char == "l":
            # Ctrl+L (clear screen)
            self.process.write(b"\x0c")
        elif char == "up":
            # Previous command in history
            self._history_previous()
        elif char == "down":
            # Next command in history
            self._history_next()

    def _history_previous(self):
        """Navigate to previous command in history"""
        if self.history_index > 0:
            self.history_index -= 1
            self._set_command_from_history()

    def _history_next(self):
        """Navigate to next command in history"""
        if self.history_index < len(self.command_history):
            self.history_index += 1
            self._set_command_from_history()

    def _set_command_from_history(self):
        """Set current command from history"""
        if 0 <= self.history_index < len(self.command_history):
            new_command = self.command_history[self.history_index]
        else:
            new_command = ""

        try:
            # Clear current line
            self.process.write(b"\x1b[2K\r")  # Clear line and return to start
            # Write new command
            self.process.write(new_command.encode())
            self.current_input = new_command
        except Exception as e:
            pass

    async def on_mouse_down(self, event):
        """Handle mouse selection start"""
        self.selection_start = (event.x, event.y)
        self.selection_end = None
        self.refresh()

    async def on_mouse_up(self, event):
        """Handle mouse selection end"""
        if self.selection_start:
            self.selection_end = (event.x, event.y)
            self._update_selection()
            self.refresh()

    async def on_mouse_move(self, event):
        """Handle mouse movement for selection"""
        if event.button and self.selection_start:
            self.selection_end = (event.x, event.y)
            self._update_selection()
            self.refresh()

    def _update_selection(self):
        """Update selected text based on selection coordinates"""
        if not self.selection_start or not self.selection_end:
            return

        start_x, start_y = self.selection_start
        end_x, end_y = self.selection_end

        # Ensure start is before end
        if (start_y > end_y) or (start_y == end_y and start_x > end_x):
            start_x, end_x = end_x, start_x
            start_y, end_y = end_y, start_y

        selected_lines = []
        for y in range(start_y, end_y + 1):
            if y < self._screen.lines:
                line = self._screen.display[y]
                if hasattr(line, '__iter__') and not isinstance(line, str):
                    # pyte >=0.9
                    if start_y == end_y:
                        selected = ''.join([char.data for char in line[start_x:end_x]])
                    elif y == start_y:
                        selected = ''.join([char.data for char in line[start_x:]])
                    elif y == end_y:
                        selected = ''.join([char.data for char in line[:end_x]])
                    else:
                        selected = ''.join([char.data for char in line])
                else:
                    # pyte <0.9
                    if start_y == end_y:
                        selected = line[start_x:end_x]
                    elif y == start_y:
                        selected = line[start_x:]
                    elif y == end_y:
                        selected = line[:end_x]
                    else:
                        selected = line
                selected_lines.append(selected)

        self.selected_text = "\n".join(selected_lines)

    async def action_copy(self):
        """Copy selected text to clipboard"""
        if self.selected_text:
            try:
                import pyperclip
                pyperclip.copy(self.selected_text)
            except ImportError:
                pass

    async def action_paste(self):
        """Paste text from clipboard"""
        try:
            import pyperclip
            text = pyperclip.paste()
            if text:
                self.process.write(text.encode())
        except ImportError:
            pass

    async def action_clear(self):
        """Clear the terminal screen"""
        try:
            self.process.write(b"\x1b[2J\x1b[H")
            self._screen.reset()
            self.refresh()
        except Exception as e:
            pass

    async def action_page_up(self):
        """Scroll one page up"""
        # Implement scrolling logic based on pyte's buffer or Textual's features
        self.scroll_position = min(
            len(self._screen.display) - self.rows,
            self.scroll_position + self.rows  # Scroll one page
        )
        self.refresh()
        self.post_message(self.Scrolled(self.scroll_position))

    async def action_page_down(self):
        """Scroll one page down"""
        self.scroll_position = max(0, self.scroll_position - self.rows)  # Scroll one page
        self.refresh()
        self.post_message(self.Scrolled(self.scroll_position))

    async def on_mouse_scroll_up(self, event):
        """Handle mouse scroll up"""
        self.scroll_position = min(
            len(self._screen.display) - self.rows,
            self.scroll_position + 3  # Adjust scroll step as needed
        )
        self.refresh()
        self.post_message(self.Scrolled(self.scroll_position))

    async def on_mouse_scroll_down(self, event):
        """Handle mouse scroll down"""
        self.scroll_position = max(0, self.scroll_position - 3)  # Adjust scroll step as needed
        self.refresh()
        self.post_message(self.Scrolled(self.scroll_position))

    def on_resize(self, event):
        """Handle terminal resize"""
        self.rows = self.size.height
        self.cols = self.size.width
        self._resize_pty()
        self.refresh()

    def unmount(self):
        """Clean up resources when widget is unmounted"""
        try:
            if self.read_task:
                self.read_task.cancel()
            if self.process:
                self.process.close()
            if self.pid:
                os.kill(self.pid, signal.SIGKILL)
        except Exception as e:
            pass
        finally:
            super().unmount()
