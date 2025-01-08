from textual.app import App
from textual.widgets import Placeholder
from textual.containers import Horizontal
from agents.command_parser import CommandParser
from langchain.agents import Tool
from langgraph.graph import StateGraph, END
from langchain_groq import ChatGroq
from langgraph.graph.state import CompiledStateGraph
from langchain.prompts import ChatPromptTemplate
from langchain.schema import BaseMessage
from pydantic import SecretStr
import subprocess
from cli.child_terminal import ChildTerminal
from agents.command_parser import CommandParser
import os
import json
from typing import Dict, List, TypedDict, Callable, Literal


class GraphState(TypedDict):
    messages: List[Dict[str, str]]  # List of all messages in conversation
    tools: Dict[str, Callable] # Dictionary of all the tools that the graph can use
    current_input: str
    action_input: dict
    action_output: str
    should_end: bool

class Shelly(App):
    def __init__(self):
        super().__init__()
        self.tools = [
            Tool(
                name="debug_code",
                func=self.debug_code,
                description="Debug the given code"
            ),
            Tool(
                name="write_code",
                func=self.write_code,
                description="Generate code based on the spec"
            ),
            Tool(
                name="run_code",
                func=self.run_code,
                description="Run a standalone file"
            ),
            Tool(
                name="open_terminal",
                func=self.open_terminal,
                description="Start a new terminal session for live code monitoring"
            ),
            Tool(
                name="conversational_response",
                func=self.conversational_response,
                description="Respond to the user input"
            )
        ]
        self.command_parser = CommandParser(self.tools)
        self.child_terminal = None
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.llm = ChatGroq(
                model="llama-3.2-8b",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)
#### TOOL DEFINITIONS #######################################################################################################
    def debug_code(self, state: GraphState) -> GraphState:
        """Debug the given code"""
        # debug here

        #print(f"Debugging: {code}")
        return state

    def write_code(self,spec: str, state: GraphState) -> GraphState:
        """Generate code based on the spec"""
        # generate code here
        print(f"generating code: {spec}")
        return state


    def run_code(self,path: str, state:GraphState):
        """A helper method to run code to pull the traceback and error_information from a single file"""
        traceback = ""
        error_information = ""
        try:
            subprocess.run(path, capture_output=True, check=True, text=True)
        except subprocess.CalledProcessError as error:
            traceback: str = error.stderr if error.stderr else str(error)
            error_information: str = str(error)
        return traceback, error_information


    def open_terminal(self, state: GraphState):
        """A helper method to open up a child terminal session for live development monitoring"""
        self.child_terminal = ChildTerminal()
        self.child_terminal.open_new_terminal()

    async def conversational_response(self, state: GraphState, input: str) -> GraphState:
        customized_prompt = ChatPromptTemplate([
            ("system", """You are a professional and specialized expert in computer programming. Your job is to respond to the user
                in a explanatory and concise manner."""),
            ("user", "{session_context}"),
            ("user", "{user_input}")
        ])
        context = state["messages"] # might have to implement context selection or context summarization
        formatted_customized_prompt = customized_prompt.format_messages(
            session_context=context, # the context from the session
            user_input = input
        )
        response: BaseMessage = await self.llm.ainvoke(formatted_customized_prompt)
        response_content = response.content if hasattr(response, 'content') else str(response)
        parsed_response: str = ""
        if isinstance(response_content, str):
            parsed_response = json.loads(response_content)
        else:
            raise ValueError("Response content is not a valid JSON string")

        if not isinstance(parsed_response, dict):
            raise ValueError("Parsed response is not a dictionary")

        state["messages"].append({"role": "user", "content": parsed_response})
        state["current_input"] = ""
        state["action_input"] = {}
        state["action_output"] = parsed_response

        return state

############################################################################################################

    def setup_graph(self) -> CompiledStateGraph:
        workflow = StateGraph(GraphState)

        workflow.add_node("parse", self.parse_message)
        workflow.add_node("execute", self.execute_action)

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
        return workflow.compile()

    async def parse_message(self, state: GraphState) -> GraphState:
        context = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in state["messages"][-5:]  # Last 5 messages for context
        ])
        parsed_response = await self.command_parser.parse_command(context)
        '''
            state["action_input"] = {
                "tool_name": parsed_response["tool_name"],
                "args": parsed_response["tool_args"]
            }
        else:
            state["current_action"] = "conversation"
            state["action_input"] = {"message": state["current_input"]}

        state["messages"].append({
            "role": "user",
            "content": state["current_input"]
        })
        '''
        tool_name = parsed_response["tool_name"]
        tool_args = parsed_response["tool_args"]
        state["action_input"] = {
            "tool_name": tool_name,
            "args": tool_args
        }
        state["messages"].append({
            "role": "user",
            "content": state["current_input"]
        })
        return state

    def should_continue(self, state: GraphState) -> Literal["continue", "end"]:
        """Determine if the workflow should continue or end"""
        return "end" if state["should_end"] else "continue"

    async def execute_action(self, state: GraphState) -> GraphState:
        """Execute an action based on the response"""
        tool_name = state["action_input"]["tool_name"]
        tool_args = state["action_input"]["args"]
        #tool = state["tools"][tool_name]
        tool = self.tools[tool_name]
        result = tool(**tool_args)
        state["action_output"] = result
        return await tool.invoke(graph_state=state, **tool_args)
            ## refactor command parser to just make a decision ->
            # responding with conversation can be one of the tools as well
    '''
    async def process_message(self, user_input: str):
        result = await self.command_parser.parse_command(user_input)
        if result["is_tool_call"]:
            # Execute the appropriate tool
            tool_name = result["tool_name"]
            tool_args = result["tool_args"]
            return await self.execute_tool(tool_name, tool_args)
        else:
            # Handle as conversation
            return await self.get_llm_response(user_input)
    '''
    async def on_mount(self) -> None:
        # Create a horizontal layout with three placeholders
        await self.mount(
            Horizontal(
                Placeholder(),
                Placeholder(),
                Placeholder()
            )
        )

if __name__ == "__main__":
    app = Shelly()
    app.run()
