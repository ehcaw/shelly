from typing import TypedDict, Optional, Dict, List, Callable, Any, Union
from pydantic import BaseModel, Field
from langchain_core.tools import Tool
from pathlib import Path
from enum import Enum
from textual import events
from textual.widgets import RichLog

class ParsedCommand(BaseModel):
    tool_name: str
    tool_args: dict


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

class ReactGraphState(TypedDict):
    messages: List[Dict[str, str]] # keep all user inputs and system inputs in here.
    tools: Dict[str, Tool]
    current_input: str # the command parser should use this. do not use messages to analyze
    action_input: Dict #input for the tool
    action_output: str # output for the tool
    current_action_list: List[ParsedCommand]
    tool_history: List
    #context_summary: str
    should_end: bool
    last_action: Optional[ParsedCommand]  # New field
    observation: Optional[str]   # New field
    action_error: Optional[str]  # New field

'''
notes
'''

class WriteMode(str, Enum):
    OVERWRITE = "overwrite"
    APPEND = "append"
    INSERT = "insert"
    MODIFY = "modify"

class LineModification(BaseModel):
    line_number: int
    content: str

class FileInput(BaseModel):
    file_path: Path = Field(..., description="Path to the file to be processed")

class DirectoryInput(BaseModel):
    directory_path: Path = Field(..., description="Path to the directory to be processed")

class CodeInput(BaseModel):
    code: Union[str, Path] = Field(..., description="Code string or path to file")
    language: Optional[str] = Field(default="python", description="Programming language")

class CodeRunInput(BaseModel):
    path: Path = Field(..., description="Path to the program to run")
    args: Optional[List[str]] = Field(default=None, description="Command line arguments")

class ConversationInput(BaseModel):
    user_input: str = Field(..., description="User's question or request")
    context_id: Optional[str] = Field(default=None, description="ID of specific context to reference")

class CodeAnalysisInput(BaseModel):
    code: Union[str, Path] = Field(..., description="Code string or path to file to analyze")
    analysis_type: Optional[str] = Field(default="general", description="Type of analysis to perform")

class CodeFixInput(BaseModel):
    code: Union[str, Path] = Field(..., description="Code to fix")
    issues: Optional[List[str]] = Field(default=None, description="Specific issues to address")

class CodeWriteInput(BaseModel):
    file_path: Path = Field(..., description="Path where to write the code")
    content: str = Field(..., description="Code content to write")
    mode: WriteMode = Field(default=WriteMode.OVERWRITE, description="How to modify the file")
    line_modifications: Optional[List[LineModification]] = Field(
        default=None,
        description="List of line modifications when using INSERT or MODIFY mode"
    )

class CodeDebugInput(BaseModel):
    code: Union[str, Path] = Field(..., description="Code to debug")
    breakpoints: Optional[List[int]] = Field(default=None, description="Line numbers for breakpoints")

class DocumentationSearchInput(BaseModel):
    query: str = Field(..., description="Search query")
    sources: Optional[List[str]] = Field(default=None, description="Specific documentation sources to search")

class ContextManagementInput(BaseModel):
    action: str = Field(..., description="Action to perform (add/update/clear)")
    context_data: Optional[Dict[str, Any]] = Field(default=None, description="Context data to manage")

class CodeExplanationInput(BaseModel):
    code: Union[str, Path] = Field(..., description="Code to explain")
    detail_level: str = Field(default="medium", description="Level of detail in explanation")

class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int

class LLMResponse(BaseModel):
    content: str
    usage: Optional[UsageInfo] = None

class CustomRichLog(RichLog):
    def action_copy(self) -> None:
            """Copy the content to clipboard."""
            import pyperclip
            pyperclip.copy(self.lines)  # Copy plain text content

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        if event.key == "ctrl+c":
            self.action_copy()
