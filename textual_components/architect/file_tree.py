from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Static, Input, Button, Tree, Label, Footer
from textual.reactive import reactive
from textual.widgets.tree import TreeNode
from textual import events
from rich.syntax import Syntax
from rich.text import Text

class FileExplorer(Tree):
    """File explorer tree component."""

    def __init__(self, files=None, architect=None, name=None, id=None, classes=None):
        super().__init__(name=name, label="Files", id=id, classes=classes)
        self.files = files or []
        self.architect = architect
    def on_mount(self):
        """Initialize the file tree."""
        self.root.expand()
        self._load_files(self.files, self.root)

    def _load_files(self, files, parent):
        """Recursively load files into the tree."""
        for file in files:
            icon = "📁 " if file["type"] == "folder" else "📄 "
            node = parent.add(icon + file["name"], data=file)
            if file["type"] == "folder" and file.get("children"):
                self._load_files(file["children"], node)
                # Auto expand src folder
                if file["name"] == "src":
                    node.expand()

    def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle node selection."""
        file_data = event.node.data
        if file_data["type"] == "file":
            self.architect.open_file(file_data)
        else:
            # Toggle folder expansion
            if event.node.is_expanded:
                event.node.collapse()
            else:
                event.node.expand()
