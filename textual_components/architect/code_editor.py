from textual.widgets import TextArea
from textual.app import ComposeResult
from typing import Callable, Optional

class CodeEditor(TextArea):
    """A code editor extending TextArea with additional functionality."""
    
    def __init__(
        self,
        text: str = "",
        *,
        language: str | None = None,
        theme: str = "monokai", #TODO: add functionalit to let user choose theme? that'd be cool
        on_change: Optional[Callable[[str], None]] = None,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        """Initialize the CodeEditor.
        
        Args:
            text: Initial text content
            language: Programming language for syntax highlighting
            theme: Color theme for the editor
            on_change: Callback function when content changes
            name: Widget name
            id: Widget ID
            classes: CSS classes
        """
        super().__init__(
            text=text,
            language=language,
            theme=theme,
            soft_wrap=False,
            tab_behavior="indent",
            show_line_numbers=True,
            name=name,
            id=id,
            classes=classes,
        )
        self.on_change_callback = on_change
        
    def watch_value(self, value: str) -> None:
        """Handle changes to editor content."""
        # Call the on_change callback if it exists
        if self.on_change_callback:
            self.on_change_callback(value)
    
    def on_mount(self) -> None:
        """Set up the editor when it's mounted."""
        super().on_mount()
        # You can add additional setup here
    
    # Add any additional methods you might need for your AI code completion feature
    def get_current_context(self) -> str:
        """Get context around the cursor for code completion."""
        cursor_pos = self.selection.end
        # Get a few lines before and after cursor
        # This would be more sophisticated in a real implementation
        return self.text
    
    def insert_completion(self, completion: str) -> None:
        """Insert a code completion at the current cursor position."""
        if not self.read_only:
            current_pos = self.selection.end
            # Insert the completion at the cursor position
            self._replace_via_keyboard(completion, *self.selection)
            # Update cursor position
            new_pos = (current_pos[0], current_pos[1] + len(completion))
            self.move_cursor(new_pos)
