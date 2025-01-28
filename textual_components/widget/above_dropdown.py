from textual.app import App, ComposeResult
from textual.widgets import Input
from textual.containers import Container
from rich.text import Text
from textual_autocomplete import AutoComplete, Dropdown, DropdownItem

class CommandDropdown(Dropdown):
    """Custom dropdown that appears below the input with proper positioning"""

    def reposition(
        self,
        input_cursor_position: int | None = None,
        scroll_target_adjust_y: int = 0,
    ) -> None:
        if self.input_widget is None:
            return

        if input_cursor_position is None:
            input_cursor_position = self.input_widget.cursor_position

        top, right, bottom, left = self.styles.margin
        x, y, width, height = self.input_widget.content_region

        # Account for horizontal scrolling in the input
        x_offset, _ = self.input_widget.scroll_offset
        cursor_screen_position = x + (input_cursor_position - x_offset)

        # Position below the input line
        line_below_cursor = y + 1 + scroll_target_adjust_y

        self.styles.margin = (
            line_below_cursor,
            right,
            bottom,
            cursor_screen_position,
        )
