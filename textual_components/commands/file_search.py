from textual.widgets import Input, Static
from textual.containers import Container
from textual.app import ComposeResult
from textual import on
from textual.message import Message
from typing import List, Optional
import os
import fnmatch

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
    DEFAULT_CSS = """
    SlashCommandPopup {
        width: 100%;
        height: auto;
        max-height: 25;  /* Limit the total height */
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
        max-height: 15;  /* Adjust this value to control visible items */
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
        
        self._cached_files = self._get_files()

    def _get_files(self, max_files: int = 100) -> List[str]:
        """Get filtered list of files or directories from current directory"""
        items = []
        cwd = os.getcwd()

        for root, dirs, filenames in os.walk(cwd, topdown=True):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in self.ignore_dirs]
            
            if self.directorySearch:
                # Only add directories
                for dir_name in dirs:
                    rel_path = os.path.relpath(os.path.join(root, dir_name), cwd)
                    items.append(rel_path + os.sep)  # Add separator to indicate directory
            else:
                # Only add files
                for filename in filenames:
                    if any(fnmatch.fnmatch(filename, pattern) for pattern in self.ignore_files):
                        continue
                    rel_path = os.path.relpath(os.path.join(root, filename), cwd)
                    items.append(rel_path)

            if len(items) >= max_files:
                return sorted(items)

        return sorted(items)

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

    def _scroll_to_selected(self):
        """Ensure the selected item is visible in the scroll view"""
        if self.selected_index is None:
            return

        container = self.query_one(".items-container")
        selected_item = self.items[self.selected_index]

        # Get container dimensions
        viewport_start = container.scroll_y
        viewport_end = viewport_start + container.size.height

        # Get item position relative to container
        item_start = selected_item.region.y - container.region.y
        item_end = item_start + selected_item.region.height

        # Calculate scroll position
        if item_start < viewport_start:
            # Scroll up to show item at top
            container.scroll_to(y=item_start)
        elif item_end > viewport_end:
            # Scroll down to show item at bottom
            container.scroll_to(y=item_end - container.size.height)

    def _select_item(self, index: int):
        """Select an item by index"""
        if not self.items:
            return

        if self.selected_index is not None:
            self.items[self.selected_index].deselect()

        index = max(0, min(index, len(self.items) - 1))
        self.items[index].select()
        self.selected_index = index

        self._scroll_to_selected()

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
        self.text_area.refresh(layout=True)
        self.remove()
        self.text_area.focus()
