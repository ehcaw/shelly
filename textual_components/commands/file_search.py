from textual.widgets import Input, Static
from textual.containers import Container
from textual.app import ComposeResult
from textual import on
from textual.message import Message
from typing import List, Optional
import os

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

    def __init__(self, text_area):
        super().__init__()
        self.text_area = text_area
        self.search_input = Input(placeholder="Search files...", classes="search-input")
        self.items_container = Container(classes="items-container")
        self.items: List[SlashCommandItem] = []
        self.selected_index: Optional[int] = None
        self._cached_files = self._get_files()

    def _get_files(self, max_files: int = 100) -> List[str]:
        """Get filtered list of files from current directory"""
        ignore_patterns = {
            # Directories to ignore
            '.git', '__pycache__', 'node_modules', 'venv', '.env',
            # File patterns to ignore
            '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll',
            '*.exe', '*.bin', '*.obj', '*.cache',
            # Add more patterns as needed
        }

        files = []
        cwd = os.getcwd()

        for root, dirs, filenames in os.walk(cwd, topdown=True):
            # Filter out ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_patterns]

            for filename in filenames:
                # Skip ignored file patterns
                if any(filename.endswith(pat.replace('*', '')) for pat in ignore_patterns):
                    continue

                rel_path = os.path.relpath(os.path.join(root, filename), cwd)
                files.append(rel_path)

                if len(files) >= max_files:
                    return sorted(files)

        return sorted(files)

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

        line_number = self.text_area.cursor_location[0]
        end = self.text_area.cursor_location[1]
        start = end - len(selected_text)

        self.text_area.refresh(layout=True)
        self.remove()
        self.text_area.styles.height = len(self.text_area.text.splitlines()) + 2
        self.text_area.focus()
