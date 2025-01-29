from textual import on
from textual.app import ComposeResult
from textual.widgets import Input, Static, TextArea, SelectionList
from textual.widgets.selection_list import Selection
from textual.containers import Container
from .above_dropdown import CommandDropdown
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
    def __init__(self, text_area: TextArea, search: str = "file"):
        super().__init__()
        self.search = search
        self.text_area = text_area
        self.input = None
        self.selection_list = None
        self.search = search

    def compose(self) -> ComposeResult:
        self.selection_list = SelectionList(self.text_area, filter=self.search)
        self.input = Input(id='search', placeholder='Type to filter')
        yield self.input
        yield self.selection_list


    @on(Input.Changed)
    def filter_list(self):
        filtered_items = []
        assert self.input is not None
        current_filter = str(self.input.value).lower()

        assert self.selection_list is not None
        if len(str(current_filter).lower()) == 0:
            self.selection_list.clear_options()
            self.selection_list.add_options(self.selection_list.curr_listings)
            return

        for item in self.selection_list.curr_listings:
            if all(word in str(item.prompt).lower() for word in current_filter.split()):
                filtered_items.append(item)

        self.selection_list.clear_options()
        if filtered_items:
            self.selection_list.add_options(filtered_items)
            self.selection_list.highlighted = 0

    @on(SelectionList.SelectionToggled)
    def select(self):
        assert self.selection_list is not None
        assert self.selection_list.highlighted is not None
        selected_option = self.selection_list.get_option_at_index(self.selection_list.highlighted)
        cursor_pos = self.text_area.cursor_location
        if cursor_pos is None:
            return

        current_line = self.text_area.document.get_line(cursor_pos[0])
        #command_start = current_line.index("/")

        self.text_area.insert(str(selected_option.prompt))
        self.text_area.action_cursor_down()
        self.remove()

    def on_key(self, event):
        if event.key == "escape":
            self.remove()
