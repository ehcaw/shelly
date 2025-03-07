from textual.containers import Container, VerticalScroll)
from textual.widgets import Static, TextArea
from textual.widget import Widget

class ChatResponse(VerticalScroll):
    content = ""
    def __init__(self):
        super().__init__()


    def compose(self):
        self.initial_text = TextArea(id="initial_text")
        yield self.initial_text

    def update_initial_text(self, new_text):
        self.initial_text.text = new_text
        self.content = new_text

    def parse_content(self):
        contents = []

    # Rerender when the response is all done
    def finalize_layout(self):
        initial_text_area = self.query_one("#initial_text", TextArea)
        if initial_text_area:
            initial_text_area.remove()
        self.vertical_scroll = VerticalScroll()
