from textual.app import App
from textual import events
from textual.widgets import Placeholder, Input, RichLog
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from agents.command_parser import CommandParser
from langchain.agents import Tool
from langgraph.graph import StateGraph, START,  END, Graph
from langgraph.checkpoint.memory import MemorySaver
from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage
from pydantic import SecretStr
import subprocess
from cli.child_terminal import ChildTerminal
from agents.command_parser import CommandParser
import os
import json
import asyncio
from typing import Dict, List, TypedDict, Callable, Literal, Optional, Any
from dotenv import load_dotenv

load_dotenv()

class GraphState(TypedDict):
    messages: List[Dict[str, str]]  # List of all messages in conversation
    tools: Dict[str, Callable] # Dictionary of all the tools that the graph can use
    current_input: str # The current user input
    action_input: dict # The input for the current action to be executed
    action_output: str # The output from the last executed action
    tool_history: List[Dict[str, Any]]
    context_summary: str
    last_tool_invoked: Optional[str]
    should_end: bool # Flag to determine if application should stop

class Shelly(App):
    CSS = """
        Vertical {
            height: 100%;
            width: 100%;
        }

        Input {
            dock: bottom;
            width: 100%;
            height: 3;  /* Fixed height for input */
        }

        RichLog {
            height: 1fr;  /* This makes it take up remaining space */
            width: 100%;
            border: solid green;  /* Optional: helps visualize the bounds */
            background: $surface;
            overflow-y: scroll;  /* Enables vertical scrolling */
        }
    """
    def __init__(self):
        super().__init__()
        self.tools = {
            "debug_code": Tool(
                name="debug_code",
                func=self.debug_code,
                description="Debug the given code"
            ),
            "write_code": Tool(
                name="write_code",
                func=self.write_code,
                description="Generate code based on the spec"
            ),
            "run_code": Tool(
                name="run_code",
                func=self.run_code,
                description="Run a standalone file"
            ),
            "open_terminal": Tool(
                name="open_terminal",
                func=self.open_terminal,
                description="Start a new terminal session for live code monitoring"
            ),
            "conversation_response": Tool(
                name="conversational_response",
                func=self.conversational_response,
                description="Respond to the user input"
            )
        }
        self.command_parser = CommandParser(list(self.tools.values()))
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
        self.graph = self.setup_graph()

    def compose(self):
        """Create ui loadout"""
        with Vertical():
               yield Input(id="user_input", placeholder="Type your message here...")
               yield RichLog(id="output", wrap=True)

    async def on_input_submitted(self, message: Input.Submitted):
        """Handle user input"""
        input_text = message.value

        # Update state and run through graph
        input_text = message.value

        # Update the current state with new input
        self.state["messages"].append({"role": "user", "content": input_text})
        self.state["current_input"] = input_text

        # Clear the input field
        input_widget = self.query_one("#user_input", Input)
        input_widget.value = ""

        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self.graph.invoke, self.state)

            # Update output log
            output_log = self.query_one("#output", RichLog)
            output_log.write(f"Response: {self.state["action_output"]}")
        except Exception as e:
            output_log = self.query_one("#output", RichLog)
            output_log.write(f"Error: {str(e)}")

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

#### TOOL DEFINITIONS #######################################################################################################
    def debug_code(self, code: str, state: GraphState) -> GraphState:
        """Debug the given code"""
        # debug here
        state["action_output"] = f"Debugging: {code}"
        state["tool_history"].append({"tool_name": "debug_code", "args": {"code": code}, "result": state["action_output"]})
        state["last_tool_invoked"] = "debug_code"
        #print(f"Debugging: {code}")
        return state

    def write_code(self,spec: str, state: GraphState) -> GraphState:
        """Generate code based on the spec"""
        # generate code here
        state["action_output"] = f"Generating code: {spec}"
        state["tool_history"].append({"tool_name": "write_code", "args": {"spec": spec}, "result": state["action_output"]})
        state["last_tool_invoked"] = "write_code"
        return state


    def run_code(self,path: str, state:GraphState, spec: str) -> GraphState:
        """A helper method to run code to pull the traceback and error_information from a single file"""
        try:
            subprocess.run(path, capture_output=True, check=True, text=True)
            state["action_output"] = f"Ran code at: {path}"
        except subprocess.CalledProcessError as error:
            traceback: str = error.stderr if error.stderr else str(error)
            error_information: str = str(error)
            state["action_output"] = f"Error running code: {traceback}"
            state["messages"].append({"role": "user", "content": str({"traceback": traceback, "error_information": error_information})})

        state["tool_history"].append({"tool_name": "run_code", "args": {"path": path}, "result": state["action_output"]})
        state["last_tool_invoked"] = "run_code"
        return state


    def open_terminal(self, state: GraphState) -> GraphState:
        """A helper method to open up a child terminal session for live development monitoring"""
        self.child_terminal = ChildTerminal()
        self.child_terminal.open_new_terminal()
        state["action_output"] = "Opened new terminal session"
        state["tool_history"].append({"tool_name": "open_terminal", "args": {}, "result": state["action_output"]})
        state["last_tool_invoked"] = "open_terminal"
        return state

    async def conversational_response(self, state: GraphState, input: str) -> GraphState:
        customized_prompt = ChatPromptTemplate([
            ("system", """You are a professional and specialized expert in computer programming. Your job is to respond to the user
                in a explanatory and concise manner."""),
            ("user", "{session_context}"),
            ("user", "{user_input}")
        ])
        state["messages"].append({"role": "user", "content": input})
        context = state["messages"] # might have to implement context selection or context summarization
        formatted_customized_prompt = customized_prompt.format_messages(
            session_context=context, # the context from the session
            user_input = input
        )
        response: BaseMessage = await self.versatile_llm.ainvoke(formatted_customized_prompt)
        response_content = response.content if hasattr(response, 'content') else str(response)
        parsed_response: str = ""
        if isinstance(response_content, str):
            parsed_response = json.loads(response_content)
        else:
            raise ValueError("Response content is not a valid JSON string")

        if not isinstance(parsed_response, dict):
            raise ValueError("Parsed response is not a dictionary")

        state["messages"].append({"role": "assistant", "content": parsed_response})
        state["current_input"] = ""
        state["action_input"] = {}
        state["action_output"] = parsed_response
        state["should_end"] = False
        state["tool_history"].append({"tool_name": "conversational_response", "args": {"input": input}, "result": parsed_response})
        state["last_tool_invoked"] = "conversational_response"

        return state

    async def summarize_context(self, state: GraphState) -> GraphState:
        return state

############################################################################################################

    def setup_graph(self):
        workflow = StateGraph(GraphState)

        #workflow.add_node("parse", lambda x: asyncio.run(self.parse_message(x)))
        #workflow.add_node("parse", self.parse_message)
        #workflow.add_node("execute", lambda x: asyncio.run(self.execute_action(x)))
        #workflow.add_node("execute", self.execute_action)

        #workflow.add_node("parse", lambda state: asyncio.create_task(self.parse_message(state)))
        #workflow.add_node("execute", lambda state: asyncio.create_task(self.execute_action(state)))

        workflow.add_node("parse", self.sudo_async_parse_message)
        workflow.add_node("execute", self.sudo_async_execute_action)

        workflow.add_edge(START, "parse")

        workflow.add_conditional_edges(
            "parse",
            self.should_continue,
            {
                "continue": "execute",
                "end": END
            }
        )

        workflow.add_conditional_edges(
            "execute",
            self.should_continue,
            {
                "continue": "parse",
                "end": END
            }
        )
        #checkpointer = MemorySaver()
        return workflow.compile()

    async def parse_message(self, state: GraphState) -> GraphState:
        try:
            context = "\n".join([
                f"{msg['role']}: {msg['content']}"
                for msg in state["messages"][-5:]
            ])

            parsed_response = await self.command_parser.parse_command(context)

            tool_name = parsed_response["tool_name"]
            tool_args = parsed_response["tool_args"]

            state["action_input"] = {
                "tool_name": tool_name,
                "args": tool_args
            }

            return state
        except Exception as e:
            state["action_output"] = f"Error parsing message: {str(e)}"
            state["should_end"] = True
            return state

    def sudo_async_parse_message(self, state: GraphState) -> GraphState:
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            parsed_response = loop.run_until_complete(self.parse_message(state))
            return state
        except Exception as e:
            state["action_output"] = f"Error parsing message: {str(e)}"
            state["should_end"] = True
            return state

        #return await self.parse_message(state)

    def should_continue(self, state: GraphState) -> Literal["continue", "end"]:
        """Determine if the workflow should continue or end"""
        return "end" if state["should_end"] else "continue"

    async def execute_action(self, state: GraphState) -> GraphState:
        """Execute an action based on the response"""
        try:
            tool_name = state["action_input"]["tool_name"]
            tool_args = state["action_input"]["args"]

            if tool_name not in self.tools:
                raise ValueError(f"Unknown tool: {tool_name}")

            tool = self.tools[tool_name]
            if asyncio.iscoroutinefunction(tool.func):
                result = await tool.ainvoke(**tool_args)
            else:
                result = tool.invoke(**tool_args)

            state["action_output"] = result
            state["should_end"] = True
            return state
        except Exception as e:
            state["action_output"] = f"Error executing action: {str(e)}"
            return state

    def sudo_async_execute_action(self, state: GraphState) -> GraphState:
        try:
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            parsed_response = loop.run_until_complete(self.execute_action(state))
            return state
        except Exception as e:
            state["action_output"] = f"Error executing action: {str(e)}"
            state["should_end"] = True
            return state

    async def on_mount(self) -> None:
        # Existing UI setu
        # Initialize and run the workflow
        self.state = GraphState(
            messages=[],
            tools=self.tools,
            current_input="",
            action_input={},
            action_output="Welcome to Shelly!",
            tool_history=[],
            context_summary="",
            last_tool_invoked=None,
            should_end=False
        )
        # Set focus to the input widget
        input_widget = self.query_one("#user_input", Input)
        input_widget.focus()

        await asyncio.sleep(0.1)
        asyncio.create_task(self.run_main_loop())

    async def run_main_loop(self) -> None:
        """Main application loop that processes the state"""
        try:
            while not self.state["should_end"]:
                await asyncio.sleep(0.1)  # Sleep for a short period to avoid a tight loop
        except asyncio.CancelledError:
            pass
        except Exception as e:
            try:
                output_log = self.query_one("#output", RichLog)
                output_log.write(f"\nError in main loop: {str(e)}")
            except NoMatches:
                print(f"\nError in main loop: {str(e)}")
        finally:
            try:
                output_log = self.query_one("#output", RichLog)
                output_log.write("\nShelly is shutting down...")
            except NoMatches:
                print("\nShelly is shutting down...")
            await asyncio.sleep(1)
            self.exit()


async def main():
    try:
        shelly = Shelly()
        await shelly.run_async()
    except Exception as e:
        print(f"Application error: {str(e)}")

if __name__ == "__main__":
    asyncio.run(main())
