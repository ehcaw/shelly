from textual.app import App
from textual import events
from agents.command_parser import CommandParser
from langchain_groq import ChatGroq
from pydantic import SecretStr
from graph import Zap
import os
import asyncio
from dotenv import load_dotenv
from textual.widgets import RichLog, TextArea
from textual.containers import Vertical

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
        self.zapper = Zap()
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

    @property
    def state(self):
        if self.zapper is None:
            return None
        return self.zapper.state

    @state.setter
    def state(self, value):
        if self.zapper is not None:
            self.zapper.state = value

    def compose(self):
        """Create ui loadout"""
        with Vertical():
               #yield Input(id="user_input", placeholder="Type your message here..")
               yield CustomTextArea(app=self, id="user_input", theme="monokai")
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

    def process_input(self, user_input: str, output_log: RichLog) -> None:
        """Process input through the graph"""
        self.compose()
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


            #output_log.write(f"\nAssistant: {self.zapper.state["action_output"]}")

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
        """Called after the app is mounted"""
        # Wait for widgets to be ready
        await asyncio.sleep(1) # This ensures all widgets are mounted

        try:
            output_log = self.query_one("#output", RichLog)
            print(f"output_log : {output_log}")
            self.zapper.output_log = output_log
            self.command_parser = CommandParser(self.zapper.tools)
            input_widget = self.query_one("#user_input", CustomTextArea)
            input_widget.focus()
        except Exception as e:
            print(f"Error in on_mount: {e}")


class CustomTextArea(TextArea):
    """A TextArea with custom key bindings."""
    def __init__(self, app: Shelly, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._shelly_app = app
        self.last_submitted_position = 0

    async def on_key(self, event):
        """Handle key press events."""
        output_log = self._shelly_app.query_one("#output", RichLog)
        if event.key == "cmnd+enter" or event.key == "ctrl+enter":
            content = self.text[self.last_submitted_position:].strip()
            self.last_submitted_position = len(content)
            if content.strip():
                output_log.write(f"input: {content}")
                self._shelly_app.process_input(content, output_log)
                #self.action_cursor_down()
        else:
            # Allow default key handling
            await super()._on_key(event)

async def main():
    try:
        shelly = Shelly()
        await shelly.run_async()
    except Exception as e:
        print(f"Application error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
