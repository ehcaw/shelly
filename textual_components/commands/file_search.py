from textual import on
from textual.app import ComposeResult
from textual.widgets import Input, Static, TextArea, SelectionList
from textual.widgets.selection_list import Selection
from textual.containers import Container
from typing import Optional, List
from functools import lru_cache
import fnmatch
import os
from pathlib import Path


class SelectionList(SelectionList):
    DEFAULT_CSS = """

    Input {
        margin: 0 1;
        border: none;
        height: 3;
    }

    .selection-list--option {
        padding: 0 1;
    }

    .selection-list--option:hover {
        background: $accent;
    }

    .selection-list--option-highlighted {
        background: $accent-darken-2;
    }

    .selection-list--option-selected {
        background: $accent-darken-1;
    }
    """

    COMPONENT_CLASSES = {
        "selection-list--option",             # Base style for each option
        "selection-list--option-highlighted", # Style for currently highlighted option
        "selection-list--option-selected"    # Style for selected options
    }

    def __init__(self, text_area: TextArea, filter: str, id: str | None = None):
        self.text_area = text_area
        self.cwd = os.getcwd()
        self.all_dirs = [Selection(str(dir), idx) for idx, dir in enumerate(self.get_all_dirs_in_cwd())]
        self.all_files = [Selection(str(dir), idx) for idx, dir in enumerate(self.get_all_files_in_cwd())]
        self.curr_listings = self.all_files if filter == "files" else self.all_dirs
        super().__init__(*self.all_dirs, id=id)  # Pass initial options to SelectionList
        self.selection_list = None
    @lru_cache
    def get_all_files_in_cwd(self, directory: Optional[str] = None, max_files=100) -> List[str]:
        cwd = directory if directory else self.cwd
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

        return sorted(str(file) for file in files)  # Sort for consistent ordering

    def get_all_dirs_in_cwd(self):
        return [d.name for d in Path(os.getcwd()).iterdir() if d.is_dir()]

    def add_options(self, items):
        """Fixed version of add_options that properly unpacks items"""
        if items:
            super().add_options(items)  # Unpack items when passing to parent
        return self

    def on_mount(self) -> None:
        text_area_region = self.text_area.region
        cursor_pos = self.text_area.cursor_location
        if cursor_pos is None:
            return
        # Position relative to text area
        self.styles.margin = (
            0,0,0,text_area_region.x
        )


class FileSearcher(Container):
    def __init__(self, text_area: TextArea, items: List[str]):
        super().__init__()
        self.text_area = text_area
        self.items = items
        self.filtered_items = items

    def compose(self) -> ComposeResult:
        self.input = Input(id='search', placeholder='Type to filter')
        self.selection_list = SelectionList(self.text_area, filter="file")
        yield self.input
        yield self.selection_list

    async def on_mount(self) -> None:
        """Focus input and select first item when mounted"""
        self.input.focus()
        if self.filtered_items:
            self.selection_list.highlighted = 0

    @on(Input.Changed)
    def filter_list(self):
        current_filter = str(self.input.value).lower()

        if not current_filter:
            self.filtered_items = self.items
        else:
            self.filtered_items = [
                item for item in self.items
                if all(word in item.lower() for word in current_filter.split())
            ]

        self.selection_list.clear_options()
        self.selection_list.add_options([
            Selection(str(item), idx)
            for idx, item in enumerate(self.filtered_items)
        ])

    def on_key(self, event) -> None:
        # Handle escape key to remove the widget
        if event.key == "escape":
            self.remove()
            # Make sure to return focus to the text area
            self.text_area.focus()
            event.prevent_default()
        elif event.key == "enter":
            # Trigger selection on enter key
            self.confirm_selection()
            event.prevent_default()

    @on(SelectionList.SelectionToggled)
    async def select(self) -> None:
        try:
            if self.selection_list.highlighted is None:
                return

            selected = self.filtered_items[self.selection_list.highlighted]
            cursor_pos = self.text_area.cursor_location
            if cursor_pos is None:
                return

            current_line = self.text_area.document.get_line(cursor_pos[0])
            command_start = current_line.index("/")

            # Replace everything after the command
            new_line = current_line[:command_start] + f"/{self.command_name} {selected}"
            self.text_area.document.set_line(cursor_pos[0], new_line)

            # Make sure we remove ourselves and return focus
            await self.remove()
            self.text_area.focus()
        except Exception as e:
            print(f"Error in select: {e}")  # Add some debug logging

    def confirm_selection(self) -> None:
        """Handle selection confirmation"""
        try:
            if self.selection_list.highlighted is None:
                return

            selected = self.filtered_items[self.selection_list.highlighted]
            cursor_pos = self.text_area.cursor_location
            if cursor_pos is None:
                return

            current_line = self.text_area.document.get_line(cursor_pos[0])
            command_start = current_line.index("/")

            # Replace everything after the command
            new_line = current_line[:command_start] + f"/file {selected}"
            self.text_area.document.set_line(cursor_pos[0], new_line)

            self.remove()
            self.text_area.focus()
        except Exception as e:
            print(f"Error in confirm_selection: {e}")

    # Add method to properly clean up
    async def on_unmount(self) -> None:
        """Called when the widget is unmounted."""
        try:
            # Make sure we cleanup any references
            self.text_area = None
            self.items = None
            self.filtered_items = None
        except Exception as e:
            print(f"Error in unmount: {e}")
