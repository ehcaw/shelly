from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Static, Input, Button, Tree, Label, Footer
from textual.reactive import reactive
from textual.widgets.tree import TreeNode
from textual import events
from rich.syntax import Syntax
from rich.text import Text

class TabButton(Button):
    """A button used for tabs."""

    def __init__(self, label, file_data=None, close_callback=None):
        super().__init__(label)
        self.file_data = file_data
        self.close_callback = close_callback

    def on_click(self):
        """Handle click events."""
        #self.architect.open_file(self.file_data) TO -DO FIX
