from textual import on
from textual.app import ComposeResult
from textual.widgets import Input, Static, TextArea, SelectionList
from textual.widgets.selection_list import Selection
from textual_autocomplete import AutoComplete, Dropdown, DropdownItem
from .above_dropdown import CommandDropdown
from typing import Optional, List
from functools import lru_cache
import fnmatch

import os
from pathlib import Path

class FileSearch(Static, can_focus=True):
    DEFAULT_CSS = """
    FileSearch {
        width: 100%;
        height: auto;
    }
    """
    def __init__(self, text_area: TextArea, file_search = True):
        super().__init__()
        self.cwd = os.getcwd()
        self.file_search = file_search
        self.text_area = text_area
        self._files = [DropdownItem(file_name) for file_name in self.files]
        self._dirs = [DropdownItem(directory_name) for directory_name in self.directories]
        self.selected = None
        self.autocomplete = None  # Store reference to autocomplete

    @property
    def files(self):
        return self.get_all_files_in_cwd()

    @property
    def directories(self):
        return self.get_all_dirs_in_cwd()

    def compose(self) -> ComposeResult:
        input_widget = Input(id='search_box', placeholder="Type to search")
        self.autocomplete = AutoComplete(
            input_widget,
            CommandDropdown(items=self._files if self.file_search else self._dirs),
            #completion_strategy="replace"
        )
        yield self.autocomplete

    def on_mount(self) -> None:
        # Debug print to confirm mounting
        print("FileSearch mounted")
        # Focus the input immediately
        self.query_one(Input).focus()

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

    @lru_cache
    def get_all_dirs_in_cwd(self):
        return [d.name for d in Path(self.cwd).iterdir() if d.is_dir()]

    def on_auto_complete_selected(self, event: AutoComplete.Selected):
        self.selected = event.item.main
        self.text_area.insert(str(self.selected))  # use highlighted instead of selected
        self.text_area.action_cursor_down()
        self.remove()


class ContextSelectionList(SelectionList):
    DEFAULT_CSS = """
    ContextSelectionList {
        background: $surface;
        border: solid $accent;
        height: auto;
        width: auto;
        min-width: 30;
        max-height: 15;
    }

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

    def __init__(self, text_area: TextArea, id: str | None = None):
        self.text_area = text_area
        self.all_dirs = [Selection(str(dir), idx) for idx, dir in enumerate(self.get_all_dirs_in_cwd())]
        super().__init__(*self.all_dirs, id=id)  # Pass initial options to SelectionList
        self.current_filter = ""
        self.search_input = None
        self.selection_list = None

    def compose(self) -> ComposeResult:
        self.search_input = Input(placeholder="Type to filter...")
        yield self.search_input
        self.selection_list = SelectionList

    @on(Input.Changed)
    def filter_list(self, event: Input.Changed):
        """Filter the list based on input text"""
        search_text = event.value.lower()

        # More detailed filtering with debug prints
        filtered = []
        for item in self.all_dirs:
            item_text = str(item.prompt).lower()
            if search_text in item_text:
                filtered.append(item)
            # Also check for partial word matches
            elif any(word in item_text for word in search_text.split()):
                filtered.append(item)

        for item in filtered:
            print(f"  + {item.prompt}")

        # Update the displayed options
        try:
            print("Clearing current options...")
            self.clear_options()

            if filtered:
                print("Adding filtered options...")
                for option in filtered:
                    try:
                        print(f"  Adding option: {option.prompt}")
                        self.add_option(option)
                    except Exception as e:
                        print(f"Error adding option {option}: {e}")
            else:
                print("No matches found, list will be empty")

            # Reset highlight if we have results
            if filtered:
                print("Resetting highlight to first item")
                self.highlighted = 0

        except Exception as e:
            print(f"Error updating options: {e}")
            import traceback
            print(traceback.format_exc())

        # Force refresh the display
        self.refresh()

    @lru_cache
    def get_all_dirs_in_cwd(self):
        return [d.name for d in Path(os.getcwd()).iterdir() if d.is_dir()]

    def add_options(self, items):
        """Fixed version of add_options that properly unpacks items"""
        if items:
            super().add_options(items)  # Unpack items when passing to parent
        return self

    def on_mount(self) -> None:
        self.search_input.focus()
        text_area_region = self.text_area.region
        cursor_pos = self.text_area.cursor_location
        if cursor_pos is None:
            return

        # Position relative to text area
        self.styles.margin = (
            0,0,0,text_area_region.x
        )

    def on_key(self, event) -> None:
        if event.key == "escape":
            self.remove()
        elif event.key == "enter" and self.highlighted is not None:
            selected_option = self.get_option_at_index(self.highlighted)
            cursor_pos = self.text_area.cursor_location
            if cursor_pos is None:
                return

            current_line = self.text_area.document.get_line(cursor_pos[0])
            command_start = current_line.index("/")

            self.text_area.delete((cursor_pos[0], command_start),
                                (cursor_pos[0], cursor_pos[1]))

            self.text_area.insert(str(selected_option.prompt))
            self.text_area.action_cursor_down()
            self.remove()
        elif event.key == "up":
            self.action_cursor_up()
        elif event.key == "down":
            self.action_cursor_down()
        else:
            if self.search_input.has_focus:
                event.prevent_default()
