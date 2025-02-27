from textual.widgets import ContentSwitcher, Static
from textual.containers import Container
from textual.message import Message
from rich_pixels import Pixels

class VerticalContentSwitcher(Container):
    """A vertical content switcher with tabs on the left side."""
    DEFAULT_CSS = """
    VerticalContentSwitcher {
        width: 100%;
        height: 100%;
        layout: horizontal;
    }

    VerticalContentSwitcher > #tabs {
        width: 15;
        height: 100%;
        dock: left;
    }

    VerticalContentSwitcher Tab {
        width: 100%;
        height: 3;
        padding: 1;
        content-align: left middle;
        border-right: tall $panel;
    }

    VerticalContentSwitcher Tab:hover {
        background: $accent;
    }

    VerticalContentSwitcher Tab.-selected {
        background: $accent;
        border-right: tall $secondary;
        text-style: bold;
    }

    VerticalContentSwitcher ContentSwitcher {
        width: 1fr;
        height: 100%;
    }
    """

    def __init__(self, chat) -> None:
        super().__init__()
        self.chat = chat
        self.tabs = Container(id="tabs")
        self.content = ContentSwitcher()

    def compose(self):
        self.tabs.styles.visible = False
        yield self.tabs
        yield self.content


    def on_mount(self) -> None:
        self.add_tab("Chat", Static(), "chat")
        self.add_tab("Architect", Static(), "architect")

    class Tab(Static):
        def __init__(self, label: str, content_id: str):
            super().__init__(label)
            self.content_id = content_id

        def on_click(self):
            self.parent.parent.switch_tab(self.content_id)

    class TabChanged(Message):
        def __init__(self, tab_id: str) -> None:
            self.tab_id = tab_id
            super().__init__()

    def add_tab(self, label: str, content: Static, tab_id: str | None = None) -> None:
        """Add a new tab and its associated content."""
        content_id = tab_id or label.lower()
        self.tabs.mount(self.Tab(label, content_id))
        content.id = content_id  # Set the id before mounting
        self.content.mount(content)

    def switch_tab(self, tab_id: str) -> None:
        """Switch to the specified tab."""
        # Update tab styling
        for tab in self.tabs.query(self.Tab):
            tab.set_class(tab.content_id == tab_id, "-selected")
        # Switch content
        self.content.current = tab_id
        self.post_message(self.TabChanged(tab_id))
