from textual.widgets import Input, Static
from textual.containers import Container
from textual.app import ComposeResult
from textual import on
from textual.message import Message
from typing import List, Optional
import os
import fnmatch
import shutil
import subprocess
from pathlib import Path
import json

class SlashCommandItem(Static):
    """Individual command item in the list"""

    class Clicked(Message):
        """Message emitted when item is clicked"""
        def __init__(self, item: "SlashCommandItem"):
            self.item = item
            super().__init__()

    def __init__(self, label: str, selected: bool = False):
        super().__init__()
        self.label = label
        self.selected = selected

    def compose(self) -> ComposeResult:
        yield Static(self.label)

    def on_mount(self):
        self.add_class("item")
        if self.selected:
            self.add_class("selected")

    def select(self):
        self.selected = True
        self.add_class("selected")

    def deselect(self):
        self.selected = False
        self.remove_class("selected")

class SlashCommandPopup(Container):
    """Main slash command component"""

    DEFAULT_CSS = """
    SlashCommandPopup {
        width: 100%;
        height: auto;
        background: $panel;
        border: solid $primary;
        padding: 1;
    }

    .search-input {
        dock: top;
        width: 100%;
        margin-bottom: 1;
    }

    .items-container {
        height: auto;
        max-height: 20;
        overflow-y: auto;
    }

    .item {
        padding: 1;
        width: 100%;
        height: 3;
    }

    .item:hover {
        background: $accent;
    }

    .selected {
        background: $accent-darken-2;
    }
    """

    class Selected(Message):
        """Message emitted when an item is selected"""
        def __init__(self, value: str):
            super().__init__()
            self.value = value

    def __init__(self, text_area, get_directories: bool = True):
        super().__init__()
        self.directorySearch = get_directories
        self.text_area = text_area
        self.search_input = Input(placeholder="Search files...", classes="search-input")
        self.items_container = Container(classes="items-container")
        self.items: List[SlashCommandItem] = []
        self.selected_index: Optional[int] = None

        # Define ignore patterns
        self.ignore_dirs = {
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

        self.ignore_files = {
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

        self._cached_files = self.find_project_files()

    def find_project_files(self, max_files=100):
        """A fast hybrid approach to find important files in a project"""
        files = []

        # Use a faster external tool like fd or ripgrep for the heavy lifting if available
        if shutil.which("fd"):
            try:
                # Fast external search for code files, limiting results
                cmd = [
                    "fd",
                    "--type", "f",                     # Only files
                    "--hidden",                        # Include hidden files
                    "--exclude", ".git",               # Common excludes
                    "--exclude", "node_modules",
                    "--exclude", "__pycache__",
                    "--exclude", "*.min.*",
                    "-e", "py", "-e", "js", "-e", "ts", "-e", "jsx", "-e", "tsx", "-e", "go", "-e", "rs",
                    "-e", "java", "-e", "c", "-e", "cpp", "-e", "h", "-e", "md", "-e", "json",
                    "--max-results", str(max_files)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    files = [f for f in result.stdout.splitlines() if f.strip()]
                    if files:
                        return sorted(files)
            except Exception:
                pass  # Fall back to Python implementation

        # Important project files to prioritize
        project_files = [
            "package.json", "pyproject.toml", "setup.py", "requirements.txt",
            "Cargo.toml", "go.mod", "Gemfile", "pom.xml", "build.gradle",
            "README.md", "README", "Dockerfile", "docker-compose.yml", ".gitignore"
        ]

        # Find project root (look for .git, etc.)
        root_dir = self.find_project_root(os.getcwd())

        # First add root level project files
        for filename in project_files:
            path = os.path.join(root_dir, filename)
            if os.path.isfile(path):
                files.append(os.path.relpath(path, os.getcwd()))
                if len(files) >= max_files:
                    return sorted(files)

        # Important directories to prioritize
        important_dirs = ["src", "app", "lib", "core", "api", "components", "utils", "tests"]

        # Prioritize high-value code extensions
        extensions = [".py", ".js", ".ts", ".jsx", ".tsx", ".vue", ".go", ".rs", ".java", ".c", ".cpp"]

        # Walk through important directories first
        for important_dir in important_dirs:
            dir_path = os.path.join(root_dir, important_dir)
            if os.path.isdir(dir_path):
                dir_files = self.scan_directory(dir_path, max_files // len(important_dirs), extensions)
                files.extend(os.path.relpath(f, os.getcwd()) for f in dir_files)

        # If we still need more files, do a fast crawl of the project root
        if len(files) < max_files:
            remaining_files = self.scan_directory(
                root_dir,
                max_files - len(files),
                extensions,
                exclude_dirs=[".git", "node_modules", "__pycache__", "build", "dist"]
            )
            files.extend(os.path.relpath(f, os.getcwd()) for f in remaining_files)

        return sorted(files[:max_files])

    def find_project_root(self,start_path):
        """Find the project root by looking for common markers"""
        current = os.path.abspath(start_path)
        while True:
            if any(os.path.exists(os.path.join(current, marker)) for marker in
                   [".git", "package.json", "pyproject.toml", "Cargo.toml"]):
                return current

            parent = os.path.dirname(current)
            if parent == current:  # Reached root directory
                return start_path
            current = parent

    def scan_directory(self,dir_path, max_files, extensions, exclude_dirs=None):
        """Efficiently scan a directory for files with specified extensions"""
        if exclude_dirs is None:
            exclude_dirs = [".git", "node_modules", "__pycache__"]

        files = []
        for root, dirs, filenames in os.walk(dir_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    files.append(os.path.join(root, filename))
                    if len(files) >= max_files:
                        return files
        return files

    def compose(self) -> ComposeResult:
        yield self.search_input
        yield self.items_container

    def on_mount(self):
        self.search_input.focus()
        self._update_items()

    def _update_items(self, filter_text: str = ""):
        """Update the displayed items based on filter"""
        self.items_container.remove_children()
        self.items.clear()

        filtered_files = [
            f for f in self._cached_files
            if all(term.lower() in f.lower() for term in filter_text.split())
        ]

        for idx, file in enumerate(filtered_files):
            item = SlashCommandItem(file, selected=(idx == 0))
            self.items.append(item)
            self.items_container.mount(item)

        self.selected_index = 0 if self.items else None

    def _select_item(self, index: int):
        """Select an item by index"""
        if not self.items:
            return

        if self.selected_index is not None:
            self.items[self.selected_index].deselect()

        index = max(0, min(index, len(self.items) - 1))
        self.items[index].select()
        self.selected_index = index

    def _confirm_selection(self):
        """Confirm the current selection"""
        if self.selected_index is not None:
            selected_value = self.items[self.selected_index].label
            self.post_message(self.Selected(selected_value))
            self.remove()

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed):
        self._update_items(self.search_input.value)

    def on_key(self, event):
        if event.key == "escape":
            self.remove()
            self.parent.styles.height = "auto"
            event.prevent_default()
        elif event.key == "enter":
            self._confirm_selection()
            event.prevent_default()
        elif event.key == "up":
            if self.selected_index is not None:
                self._select_item(self.selected_index - 1)
            event.prevent_default()
        elif event.key == "down":
            if self.selected_index is not None:
                self._select_item(self.selected_index + 1)
            event.prevent_default()

    @on(SlashCommandItem.Clicked)
    def on_item_clicked(self, event: SlashCommandItem.Clicked):
        clicked_item = event.control
        clicked_index = self.items.index(clicked_item)
        self._select_item(clicked_index)
        self._confirm_selection()

    def confirm_selection(self) -> None:
        self.focus()
        items = self.query("Static.item")
        if not items or self.selected_index >= len(items):
            return

        selected = items[self.selected_index]
        # Get the text content from the Static widget
        selected_text = selected.label  # or selected.get_content()

        cursor_pos = self.text_area.cursor_location
        if cursor_pos is None:
            return

        self.text_area.insert(selected_text)

        end = self.text_area.cursor_location[1]
        self.text_area.refresh(layout=True)
        self.remove()
        self.text_area.styles.height = "auto"
        self.text_area.focus()
