from typing import Any, Optional, Tuple, Union
from dataclasses import dataclass
import inspect

from textual.widgets import Footer, Input, Label
from textual.containers import Horizontal, Vertical
from rich.console import RenderableType
from textual.reactive import reactive, Reactive
from textual.message import Message
from textual.app import RenderResult


@dataclass
class Field:
    name: str
    type: Any
    has_spaces: bool = False
    value: str = ""

    def __str__(self) -> str:
        return f"<{self.name}: {self.type.__name__}>"


@dataclass
class Command:
    name: str
    fields: Tuple[Field, ...]
    on_submit: callable


class CommandFooter(Footer):
    """A custom footer widget that handles commands with input fields."""

    DEFAULT_CSS = """
    #command_input {
        min-height: 4;
    }
    .align-center {
        align: center middle;
    }
    .ml-2 {
        margin-left: 2;
    }
    """

    command: Reactive[Optional[Command]] = reactive[Optional[Command]](None)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.height_class = "h-4"

    def render(self) -> RenderResult:
        if self.command is not None:
            return ""
        return super().render()

    def watch_command(self, command: Optional[Command]) -> None:
        """Watch for changes in the command reactive variable."""
        self.update(command)

    @property
    def value(self) -> Optional[str]:
        """Get the current value of all fields."""
        if self.command:
            ans = [f.value for f in self.command.fields if f.value]
            return " ".join(ans)
        return None

    @property
    def placeholder(self) -> Optional[str]:
        """Get the placeholder text for the input field."""
        if self.command:
            ans = [str(f) for f in self.command.fields]
            return " ".join(ans)
        return None

    def _extract_values(self, *args: str) -> Optional[tuple]:
        """Extract and convert input values according to field types."""
        if not args or args[0] is None or not self.command:
            return None

        values = []
        fields = self.command.fields

        try:
            for i in range(len(fields) - 1, -1, -1):
                field = fields[i]
                if field.has_spaces:
                    if i == len(fields) - 1:
                        values.append(" ".join(args))
                    else:
                        values.append(" ".join(args[:i + 1]))
                    break
                else:
                    value = args[i]
                    if field.type == bool:
                        values.append(value.lower() in ("y", "yes", "true"))
                    else:
                        values.append(field.type(value))

            return tuple(reversed(values))
        except (ValueError, IndexError):
            return None

    def update(self, command: Optional[Command]) -> None:
        """Update the footer with new command information."""
        # Remove existing command footer if command is None
        try:
            if container := self.query_one("#command_footer"):
                container.remove()
        except Exception:
            pass

        if command is None:
            self.remove_class(self.height_class)
            return

        # Create new command footer
        input_field = Input(
            value=self.value or "",
            placeholder=self.placeholder or "",
            classes="w-pct-100 h-3"
        )

        command_input = Horizontal(
            Label(command.name, classes="align-center"),
            Vertical(
                input_field,
                Label(self.placeholder or "", classes="w-pct-100 h-1 ml-2"),
                classes="w-pct-100 h-pct-100",
            ),
            classes="align-center h-pct-20",
            id="command_input",
        )

        container = Vertical(
            command_input,
            id="command_footer",
            classes="align-center h-pct-100 w-pct-100",
        )

        self.mount(container)
        self.add_class(self.height_class)
        self.screen.set_focus(input_field)

    def on_key(self, event) -> None:
        """Handle key events."""
        if event.key == "escape":
            self.command = None

    async def on_input_submitted(self, message: Message) -> None:
        """Handle input submission."""
        if self.command is None:
            return

        try:
            callback = self.command.on_submit
            tokens = message.value.split()
            if values := self._extract_values(*tokens):
                result = callback(values)
                if inspect.iscoroutine(result):
                    await result
        except Exception as e:
            # You might want to handle or log the error here
            print(f"Error processing command: {e}")

        self.command = None
