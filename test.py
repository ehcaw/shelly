from textual.app import App, ComposeResult
from textual.widgets import Static, Button, Header
from textual.containers import VerticalScroll
from rich.text import Text
from textual_components.widget.chatbox import ChatboxContainer, Chatbox

class ScrollTest(App):
    CSS = """
    Screen {
        layout: vertical;
    }

    VerticalScroll {
        height: 1fr;
        width: 100%;
        border: solid red;
        background: yellow 30%;
    }

    Static {
        width: 100%;
        margin: 1;
        padding: 1;
    }

    Button {
        margin: 1;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        yield Button("Add Message", id="add-btn")
        self.scroll = VerticalScroll()
        yield self.scroll

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        await self.add_message(f"Test message {len(self.scroll.children)}")

    async def add_message(self, content: str) -> None:
        #message = Static(Text(content))
        chatbox = Chatbox(content=content)
        container = ChatboxContainer(chatbox)
        await self.scroll.mount(container)
        self.scroll.scroll_end(animate=False)

if __name__ == "__main__":
    app = ScrollTest()
    app.run()
