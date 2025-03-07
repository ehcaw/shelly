from textual.widgets import Input
from textual.containers import Container
from textual import on
from .document_store import DocumentStore

class CommandPopup(Container):
    """Popup for entering commands."""
    DEFAULT_CSS = """
    CommandPopup {
        width: 50%;
        height: auto;
        background: $surface;
        border: solid $primary;
        dock: top;
        margin-top: 2;
        padding: 1;
    }
    
    #command-input {
        width: 100%;
        margin: 0 1;
    }
    """

    def __init__(self) -> None:
        super().__init__()
        self.input = Input(id="command-input", placeholder="Enter command (e.g. @doc <url>)")

    def compose(self):
        yield self.input

    @on(Input.Submitted)
    def handle_command(self, event: Input.Submitted) -> None:
        """Handle command input submission."""
        command = event.value.strip()
        if command.startswith("@doc "):
            url = command[5:].strip()
            self.process_doc_command(url)
        self.remove()

    async def process_doc_command(self, url: str) -> None:
        """Process the @doc command to scrape and store URL content."""
        try:
            self.app.notify(f"Processing documentation from: {url}")
            doc_store = DocumentStore()
            await doc_store.add_url_content(url)
            self.app.notify("Documentation successfully added to vector store")
        except Exception as e:
            self.app.notify(f"Error processing URL: {str(e)}", severity="error")
