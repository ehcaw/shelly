from langchain.agents import Tool
from langchain.agents import AgentExecutor
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field
from typing import TypedDict, Annotated, List
import sys
import os
import subprocess
from ..cli.child_terminal import ChildTerminal


class AgentState(TypedDict):
    messages: list[str]
    current_action: str

def debug_code(code: str) -> str:
    """Debug the given code"""
    # debug here
    return f"Debugging: {code}"

def write_code(spec: str) -> str:
    """Generate code based on the spec"""
    # generate code here
    return f"generating code: {spec}"

def run_code(path: str):
    try:
        subprocess.run(path, capture_output=True, check=True, text=True)
    except subprocess.CalledProcessError as error:
        traceback: str = error.stderr if error.stderr else str(error)
        error_information = str(error)

def open_terminal():
    child_terminal = ChildTerminal()
    child_terminal.open_new_terminal()


tools = [
    Tool(
        name="debug_code",
        func=debug_code,
        description="Debug the given code"
    ),
    Tool(
        name="write_code",
        func=write_code,
        description="Generate code based on the spec"
    ),
    Tool(
        name="run_code",
        func=run_code,
        description="Run a standalone file"
    ),
    Tool(
        name="open_terminal",
        func=open_terminal,
        description="Start a new terminal session for live code monitoring"
    )
]

class ErrorExplanation(BaseModel):
    error_type: str = Field(description="The type of error encountered")
    explanation: str = Field(description="Detailed explanation of the error")
    suggested_fixes: List[str] = Field(description="List of potential fixes for the error")
    code_segments: List[str] = Field(description="List of code segments to fix the errors mentioned")

class Zapper:
    def __init__(self):
        super().__init__()
        self.graph = self.setup_graph()

    def setup_graph(self):
        graph = StateGraph(AgentState)
        graph.add_node("process_message", self.process_message)
        graph.add_node("execute_action", self.execute_action)

        graph.add_edge("process_message", "execute_action")
        graph.add_edge("execute_action", END)

        return graph.compile()

    async def process_message(self, state: AgentState) -> AgentState:
            """Process the user message and determine action"""
            # Add LLM logic here to determine if this is a command or conversation
            message = state["messages"][-1]
            if message.startswith("/"):
                state["current_action"] = "command"
            else:
                state["current_action"] = "conversation"
            return state

    async def execute_action(self, state: AgentState) -> AgentState:
        """Execute the determined action"""
        if state["current_action"] == "command":
            # Handle command execution
            command = state["messages"][-1][1:]  # Remove the / prefix
            # Add command execution logic
            pass
        else:
            # Handle conversation with LLM
            pass
        return state
