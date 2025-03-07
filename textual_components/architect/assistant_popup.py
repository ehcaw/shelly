from textual.widgets import Button, TextArea, Label, Static
from textual.containers import Container, Horizontal
from textual.app import ComposeResult
from rich.console import RenderableType
from textual.message import Message

from langchain.prompts import ChatPromptTemplate

class CodeQuerySubmitted(Message):
    """Event emitted when a code query is submitted."""

    def __init__(self, code: str, query: str) -> None:
        self.code = code
        self.query = query
        super().__init__()

system_prompt = ChatPromptTemplate.from_messages([
    ("system", """You are an expert programming assistant embedded directly in a code editor. Your task is to respond to user queries about specific code selections and generate code solutions.

    When responding to a user, follow this structured format:

    1. BRIEF EXPLANATION:
       Begin with a concise explanation of what you're doing and how it addresses the user's query.

    2. CODE SOLUTION:
       ```language
       // Your generated code here - use appropriate syntax highlighting and comments
       // Make sure it's well-formatted and follows best practices
       ```

    3. ADDITIONAL CONTEXT (optional):
       * How the solution works
       * How it integrates with their existing code
       * Potential edge cases or considerations
       * Alternative approaches if relevant

    IMPORTANT GUIDELINES:
    - Focus on the specific code selection provided
    - Write production-quality, maintainable code
    - Include proper error handling where appropriate
    - Match the coding style of the user's existing code
    - When you need more context, acknowledge it but provide the best possible solution
    - Keep explanations technical but clear
    - Don't apologize or use excessive phrases like "I'd be happy to help"

    Remember: Your primary purpose is to generate working, well-formatted code solutions that can be directly integrated into the user's codebase.
    ```

    This system prompt instructs the LLM to:
    1. Start with a concise explanation
    2. Provide well-formatted code in a code block
    3. Add supplementary information as needed
    4. Focus specifically on the selected code and user query
    5. Maintain a professional, direct tone focused on code solutions
    6. Follow best practices for code generation

    You can adjust the level of detail or specific focuses based on your users' typical needs."""),
    ("system", """Here is the code:
    {code_snippet}
    """),
    ("user", "{query}")
])

class AssistantPopup(Static):
    """A popup dialog that floats above the editor for querying about selected code."""

    DEFAULT_CSS = """
    AssistantPopup {
        width: 60%;
        height: 50%;
        background: $surface;
        border: tall $accent;
        padding: 1;
        layer: overlay;
        align: center middle;
    }

    #popup-title {
        text-align: center;
        background: $accent;
        color: $text;
        padding: 1;
        width: 100%;
    }

    #selected-code {
        margin-top: 1;
        height: 30%;
        margin-bottom: 1;
    }

    #query-input {
        height: 30%;
        margin-bottom: 1;
    }
    #response {
        min-height: 30%;
        height: 1fr;
        overflow-y: scroll;
    }

    #button-container {
        width: 100%;
        align: center middle;
        padding-top: 1;
    }

    #button-container Button {
        margin: 0 1;
    }
    """

    def __init__(self, selected_code: str, llm):
        super().__init__()
        self.selected_code = selected_code
        self.llm = llm

    def compose(self) -> ComposeResult:
        # Debug to verify self.selected_code has a value
        yield TextArea(id="selected-code", text=self.selected_code, language="python", read_only=True)
        yield TextArea(id="query-input")  # <-- This ID must match exactly
        yield TextArea(id="response", text="", language='python', read_only=True)

        with Container(id="button-container"):
            with Horizontal():
                yield Button("Submit", variant="primary", id="submit-button")
                yield Button("Cancel", variant="error", id="cancel-button")

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "submit-button":
            query = self.query_one("#query-input", TextArea).text
            # Emit a message instead of returning a value
            #self.emit_no_wait(CodeQuerySubmitted(self.selected_code, query))
            await self.generate_response(self.selected_code, query)

        # Remove the popup from the DOM
        #self.remove()

    async def generate_response(self, code_snippet, query):
        # Add loading indicator
        response_box = self.query_one("#response", TextArea)
        response_box.text = "Generating response..."

        try:
            formatted_prompt = system_prompt.format_messages(code_snippet=code_snippet, query=query)
            # Assuming llm.invoke is async
            response = await self.llm.ainvoke(formatted_prompt)
            # Update the response box
            response_box.text = response.content
        except Exception as e:
            response_box.text = f"Error generating response: {str(e)}"
