from textual.widgets import TextArea
from typing import Callable, Optional
from ..architect.assistant_popup import AssistantPopup, CodeQuerySubmitted

from langchain_groq import ChatGroq


class CodeEditor(TextArea):
    """A code editor extending TextArea with additional functionality."""

    BINDINGS = [
        ("ctrl+shift+a", "ask_about_selection", "Ask about selection"),
         ("cmd+shift+;", "show_command_popup", "Show command popup"),  # New binding
    ]

    def __init__(
        self,
        text: str = "",
        llm: ChatGroq | None= None,
        *,
        language: str | None = "python",
        theme: str = "monokai",
        on_change: Optional[Callable[[str], None]] = None,
        on_query: Optional[Callable[[str, str], None]] = None,  # Callback for code queries
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
    ) -> None:
        super().__init__(
            id=id,
            text=text,
            language=language,
            theme=theme,
            soft_wrap=False,
            tab_behavior="indent",
            show_line_numbers=True,
            name=name,
            classes=classes,
        )
        self.on_change_callback = on_change
        self.on_query_callback = on_query
        self.on_change_callback = on_change
        self.llm = llm


    def on_text_area_changed(self, event: TextArea.Changed) -> None:
        """Handle changes to editor content."""
        if self.on_change_callback:
            self.on_change_callback(self.text)

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

    async def action_ask_about_selection(self) -> None:
        """Handle the 'ask about selection' action."""
        # Get selected text correctly from TextArea
        selected_text = self.selected_text

        if selected_text:
            # Create the popup with the selected text
            popup = AssistantPopup(selected_text, self.llm)

            # Mount the popup to the app's screen
            await self.app.mount(popup)

            # Debug to see if popup was created correctly
            self.app.log(f"Popup created with: {selected_text[:20]}...")
            self.app.log(f"Popup widget tree: {popup.tree}")

            # Focus the query input
            popup.query_one("#query-input").focus()
        else:
            self.app.notify("No code selected. Please select some code first.")

    def on_code_query_submitted(self, event: CodeQuerySubmitted) -> None:
        """Handle the code query submission."""
        if self.on_query_callback:
            self.on_query_callback(event.code, event.query)
        else:
            # Default implementation if no callback
            self.app.notify(f"Query: {event.query} about selected code")

    def set_language(self, language: str | None):
        if language:
            self.language = language
