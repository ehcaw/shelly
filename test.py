from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, OptionList, TextArea, Input
from textual.widgets.option_list import Option, Separator
from textual_components.widget.file_search import SelectionList, FileSearcher
from textual_autocomplete import AutoComplete, Dropdown, DropdownItem
from pathlib import Path


class OptionListApp(App[None]):

    def compose(self) -> ComposeResult:
        yield Header()
        text_area = TextArea()
        yield text_area
        yield FileSearcher(text_area)
        yield Footer()


if __name__ == "__main__":
    OptionListApp().run()
