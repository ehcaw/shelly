from typing import TypedDict, Optional, Dict, List, Callable, Any
from pydantic import BaseModel

class ParsedCommand(TypedDict):
    tool_name: Optional[str]
    tool_args: Optional[Dict]

class ParsedCommandList(BaseModel):
    tools: List[ParsedCommand]

class GraphState(TypedDict):
    messages: List[Dict[str, str]]  # List of all messages in conversation
    tools: Dict[str, Callable] # Dictionary of all the tools that the graph can use
    current_input: str # The current user input
    action_input: dict | ParsedCommand # The input for the current action to be executed
    action_output: str # The output from the last executed action
    current_action_list: List[ParsedCommand]
    tool_history: List[Dict[str, Any]]
    context_summary: str
    last_tool_invoked: Optional[str]
    should_end: bool # Flag to determine if application should stop
