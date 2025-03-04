import difflib
from typing import Optional, List, Tuple

from textual.app import App, ComposeResult
from textual.widgets import Static, Button, Footer
from textual.containers import Vertical, Horizontal, ScrollableContainer

class DiffViewer(ScrollableContainer):
    def __init__(self, diff_text: str) -> None:
        super().__init__()
        self.diff_text = diff_text
    async def on_mount(self):
        await self.mount(Static(self.diff_text, id="diff_viewer", expand=True, markup=False))

class ApplyChangesWidget(Vertical):
    DEFAULT_CSS = """
    .Button {
        height: 5;
        width: 5;
    }
    """
    def __init__(self, original: str, modified: str, file_name: Optional[str],
                 edit_type: str = "full_replacement",
                 start_line: int = 0,
                 end_line: int = 0) -> None:
        super().__init__()
        self.original = original
        self.modified = modified
        self.file_name = file_name if file_name else "Original"
        self.edit_type = edit_type
        self.start_line = start_line
