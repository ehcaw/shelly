from textual.app import App
from textual import events
from agents.command_parser import CommandParser
from langchain_groq import ChatGroq
from pydantic import SecretStr
from graph import Zap
import os
import asyncio
from dotenv import load_dotenv
from textual.widgets import RichLog, Input
from textual.containers import Horizontal, Vertical


load_dotenv()

class Shelly(App):
    CSS = """
        Vertical {
            height: 100%;
            width: 100%;
        }

        Input {
            dock: top;
            width: 100%;
            height: 3;
            margin: 1;
            border: solid $accent;
        }

        Input:focus {
            border: double $accent;
        }

        RichLog {
            height: 1fr;
            width: 100%;
            border: solid $accent;
            background: $surface;
            overflow-y: scroll;
            padding: 1;
            margin: 1;
        }

        #output {
            scrollbar-color: $accent $surface-darken-2;
        }
        """
    def __init__(self):
        super().__init__()
        self.child_terminal = None
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.versatile_llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)
        self.simple_llm = ChatGroq(
            model="llama3-8b-8192",
            api_key=SecretStr(api_key),
            temperature=0,
            stop_sequences=None
        )
        self.zapper = Zap()
        self.command_parser = CommandParser(self.zapper.tools)

    @property
    def state(self):
        return self.zapper.state
    @state.setter
    def state(self, value):
        self.zapper.state = value

    def compose(self):
        """Create ui loadout"""
        with Vertical():
               yield Input(id="user_input", placeholder="Type your message here...")
               yield RichLog(id="output", wrap=True)



    def on_key(self, event) -> None:
            """Handle key events"""
            # Add any key-based controls here
            if event.key == "ctrl+c":
                self.state["should_end"] = True

    async def on_key_pressed(self, event: events.Key) -> None:
        if event.key == "c" and event.control:
            self.state["should_end"] = True

    async def on_shutdown(self) -> None:
        """Clean up when the application is shutting down"""
        # Add any cleanup code here
        if self.child_terminal:
            self.child_terminal.kill_tmux_session()

            """Debug method to check if everything is properly initialized"""
            output_log = self.query_one("#output", RichLog)

            output_log.write("\n[yellow]Checking setup...[/yellow]")
            output_log.write(f"\nZapper initialized: {hasattr(self, 'zapper')}")
            output_log.write(f"\nState initialized: {hasattr(self, 'state')}")
            output_log.write(f"\nAvailable tools: {len(self.zapper.tools) if hasattr(self.zapper, 'tools') else 'No tools'}")
            output_log.write(f"\nGraph nodes: {len(self.zapper.graph.nodes) if hasattr(self.zapper, 'graph') else 'No graph'}")

    async def on_input_submitted(self, message: Input.Submitted) -> None:
        """Handle input submission"""
        input_widget = self.query_one("#user_input", Input)
        output_log = self.query_one("#output", RichLog)

        user_input = message.value
        if not user_input.strip():  # Skip empty inputs
            return

        input_widget.value = ""

        # Show processing status

        # Use call_later to allow the UI to update
        self.process_input(user_input, output_log)

    def process_input(self, user_input: str, output_log: RichLog) -> None:
        """Process input through the graph"""
        try:

            # Update state with user input
            self.zapper.state["messages"] = self.zapper.state["messages"] + [{
                "role": "user",
                "content": user_input
            }]

            # Invoke the graph
            # Debug response
            """
            for event in self.zapper.graph.stream(self.zapper.state):
                for value in event.values():
                    output_log.write(f"\nAssistant: {value}")
            """
            self.zapper.graph.invoke(self.zapper.state)
            output_log.write(f"\nAssistant: {self.zapper.state["action_output"]}")

        except Exception as e:
            import traceback
            output_log.write(f"\n[red]Error: {str(e)}[/red]")
            output_log.write(f"\n[dim]{traceback.format_exc()}[/dim]")

    async def check_setup(self) -> None:
        """Debug method to check if everything is properly initialized"""
        output_log = self.query_one("#output", RichLog)
        output_log.write(f"\nAvailable tools: {len(self.zapper.tools) if hasattr(self.zapper, 'tools') else 'No tools'}")
        output_log.write(f"\nGraph nodes: {len(self.zapper.graph.nodes) if hasattr(self.zapper, 'graph') else 'No graph'}")

    async def on_mount(self) -> None:
    # Existing UI setu
        # Initialize and run the workflow
        # Set focus to the input widget
        input_widget = self.query_one("#user_input", Input)
        input_widget.focus()

async def main():
    try:
        shelly = Shelly()
        await shelly.run_async()
    except Exception as e:
        print(f"Application error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
