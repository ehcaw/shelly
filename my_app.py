from textual.app import App

from langchain_groq import ChatGroq
from pydantic import SecretStr

from textual.widgets import RichLog, Header
from textual.containers import Vertical, Grid, ScrollableContainer
from textual_components.terminal_widget import PtyTerminal, TabbedTerminals
from textual.message import Message
from textual.widgets import Static, TextArea, SelectionList
from dataclasses import dataclass
from typing import Callable

from functools import wraps, lru_cache
import time
import fnmatch
import os
import asyncio
from pathlib import Path
from dotenv import load_dotenv

from textual_components.chat.chat import Chat
from agents.zapper import Zapper


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


    def action_new_terminal(self):
        """Add a new terminal tab."""
        terminal_tabs = self.query_one(TabbedTerminals)
        terminal_tabs.add_terminal()

    def action_close_terminal(self):
        """Close the current terminal tab."""
        terminal_tabs = self.query_one(TabbedTerminals)
        terminal_tabs.action_close_terminal()

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
        chat.debug_log = debug_log


@dataclass
class Command:
    """Represents a command that can be triggered"""
    name: str
    description: str
    handler: Callable
    args: list = None

# this class has to stay here because we have to pass a reference of shelly to it (preventing circular imports)
class CustomTextArea(TextArea):
    """A TextArea with custom key bindings."""
    def __init__(self, app: Shelly, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.show_line_numbers=True
        self._shelly_app = app
        self.last_submitted_position = 0
        '''
        self.commands: Dict[str, Command] = {
            "!help": Command(
                name="help",
                description="Show help message",
                handler=self.show_help
            ),
            "!clear": Command(
                name="clear",
                description="Clear output",
                handler=self.clear_output
            ),
            "!run": Command(
                name="run",
                description="Run code",
                handler=self.run_code,
                args=["filepath"]
            )
        }'''

    @lru_cache
    def get_all_files_in_cwd(self, max_files=100):
        cwd = os.getcwd()
        files = []

        # Extensive list of directories to ignore
        ignore_dirs = {
            # Version Control
            '.git', '.svn', '.hg', '.bzr',

            # Python
            '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
            'venv', '.venv', 'env', '.env', '.tox',

            # Node.js / JavaScript
            'node_modules', 'bower_components',
            '.next', '.nuxt', '.gatsby',

            # Build directories
            'dist', 'build', '_build', 'public/build',
            'target', 'out', 'output',
            'bin', 'obj',

            # IDE and editors
            '.idea', '.vscode', '.vs',
            '.settings', '.project', '.classpath',

            # Dependencies
            'vendor', 'packages',

            # Coverage and tests
            'coverage', '.coverage', 'htmlcov',

            # Mobile
            'Pods', '.gradle',

            # Misc
            'tmp', 'temp', 'logs',
            '.sass-cache', '.parcel-cache',
            '.cargo', 'artifacts'
        }

        # Extensive list of file patterns to ignore
        ignore_files = {
            # Python
            '*.pyc', '*.pyo', '*.pyd',
            '*.so', '*.egg', '*.egg-info',

            # JavaScript/Web
            '*.min.js', '*.min.css',
            '*.chunk.js', '*.chunk.css',
            '*.bundle.js', '*.bundle.css',
            '*.hot-update.*',

            # Build artifacts
            '*.o', '*.obj', '*.a', '*.lib',
            '*.dll', '*.dylib', '*.so',
            '*.exe', '*.bin',

            # Logs and databases
            '*.log', '*.logs',
            '*.sqlite', '*.sqlite3', '*.db',
            '*.mdb', '*.ldb',

            # Package locks
            'package-lock.json', 'yarn.lock',
            'poetry.lock', 'Pipfile.lock',
            'pnpm-lock.yaml', 'composer.lock',

            # Environment and secrets
            '.env', '.env.*', '*.env',
            '.env.local', '.env.development',
            '.env.test', '.env.production',
            '*.pem', '*.key', '*.cert',

            # Cache files
            '.DS_Store', 'Thumbs.db',
            '*.cache', '.eslintcache',
            '*.swp', '*.swo',

            # Documentation build
            '*.pdf', '*.doc', '*.docx',

            # Images and large media
            '*.jpg', '*.jpeg', '*.png', '*.gif',
            '*.ico', '*.svg', '*.woff', '*.woff2',
            '*.ttf', '*.eot', '*.mp4', '*.mov',

            # Archives
            '*.zip', '*.tar', '*.gz', '*.rar',

            # Generated sourcemaps
            '*.map', '*.css.map', '*.js.map'
        }

        for root, dirs, filenames in os.walk(cwd, topdown=True):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for filename in filenames:
                # Skip files matching ignore patterns
                if any(fnmatch.fnmatch(filename, pattern) for pattern in ignore_files):
                    continue

                # Get relative path
                rel_path = os.path.relpath(os.path.join(root, filename), cwd)

                # Skip paths that contain any of the ignored directory names
                # (handles nested cases like 'something/node_modules/something')
                if any(ignored_dir in rel_path.split(os.sep) for ignored_dir in ignore_dirs):
                    continue

                files.append(rel_path)

                if len(files) >= max_files:
                    return files

        return sorted(files)  # Sort for consistent ordering

    @lru_cache
    def get_all_dirs_in_cwd(self):
        cwd = Path.cwd()
        return [d.name for d in cwd.iterdir() if d.is_dir()]



    async def on_key(self, event):
        """Handle key press events."""
        output_log = self._shelly_app.query_one("#output", CustomRichLog)
        if event.key == "alt+enter" or event.key == "ctrl+enter":
            content = self.text[self.last_submitted_position:].strip()
            self.last_submitted_position = len(content)
            if content.strip():
                output_log.write(f"input: {content}")
                self._shelly_app.process_input(content, output_log)
                self.action_cursor_down()
        else:
            # Allow default key handling
            await super()._on_key(event)


class ContextSelectionList(SelectionList):
    def __init__(self, *items, text_area: TextArea, id: str | None = None):
        super().__init__(*items, id=id)
        self.text_area = text_area
    def on_key(self, event) -> None:
        if event.key == "enter" and self.highlighted is not None:
                selected_option = self.get_option_at_index(self.highlighted)
                self.text_area.insert(str(selected_option.prompt))  # use highlighted instead of selected
                self.text_area.action_cursor_down()
                self.remove()
        elif event.key == "escape":
            self.remove()

    #def on_click(self) -> None:

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

'''
async def main():
    try:
        shelly = Shelly()
        await shelly.run_async()
    except Exception as e:
        print(f"Application error: {str(e)}")
'''

def main():
    shelly = Shelly()
    shelly.run()

if __name__ == "__main__":
    main()
