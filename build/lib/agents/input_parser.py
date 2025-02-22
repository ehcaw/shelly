from typing import Dict, List, Any, Optional, Union
from pydantic import BaseModel, SecretStr
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from langchain.tools import Tool
import os
from dotenv import load_dotenv
from pathlib import Path
import logging
from shelly_types.types import ParsedCommand, ParsedCommandList, GraphState, ReactGraphState

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CommandParser:
    def __init__(self, available_tools: Dict[str, Tool]):
        self.available_tools = available_tools
        self.tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in available_tools.values()
        ])

        # Initialize LLM and prompt template
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        self.llm = ChatGroq(
            model="llama-3.2-3b-preview",
            api_key=SecretStr(api_key),
            temperature=0.,
            stop_sequences=None
        )

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a command parser that converts user input into tool calls.
                Available tools:
                {tool_descriptions}

                Return a JSON array of tool objects in this format ONLY:
                [
                    {
                        "tool_name": "tool_name",
                        "tool_args": {
                            "arg1": "value1",
                            "arg2": "value2"
                        }
                    }
                ]
                """),
            ("user", "{user_input}")
        ])

    def parse_command(self, state: Union[GraphState, ReactGraphState]) -> ParsedCommandList:
        """Parse the current input from the state and return a ParsedCommandList"""
        user_input = state["current_input"]

        if not user_input:
            return ParsedCommandList(tools=[])

        lines = user_input.strip().split('\n')
        all_tools: List[ParsedCommand] = []
        context = {}

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle file commands
            if line.startswith('/file '):
                file_path = line.split('/file ', 1)[1].strip()
                try:
                    path = Path(file_path).resolve()
                    if path.exists():
                        context['current_file'] = str(path)
                        all_tools.append(ParsedCommand(
                            tool_name="load_file",
                            tool_args={"file_path": str(path)}
                        ))
                    else:
                        all_tools.append(ParsedCommand(
                            tool_name="conversation_response",
                            tool_args={"user_input": f"File not found: {file_path}"}
                        ))
                except Exception as e:
                    logger.error(f"Error processing file path: {e}")
                    all_tools.append(ParsedCommand(
                        tool_name="conversation_response",
                        tool_args={"user_input": f"Invalid file path: {file_path}"}
                    ))

            # Handle directory commands
            elif line.startswith('/dir '):
                dir_path = line.split('/dir ', 1)[1].strip()
                try:
                    path = Path(dir_path).resolve()
                    if path.is_dir():
                        context['current_dir'] = str(path)
                        all_tools.append(ParsedCommand(
                            tool_name="load_directory",
                            tool_args={"directory_path": str(path)}
                        ))
                    else:
                        all_tools.append(ParsedCommand(
                            tool_name="conversation_response",
                            tool_args={"user_input": f"Directory not found: {dir_path}"}
                        ))
                except Exception as e:
                    logger.error(f"Error processing directory path: {e}")
                    all_tools.append(ParsedCommand(
                        tool_name="conversation_response",
                        tool_args={"user_input": f"Invalid directory path: {dir_path}"}
                    ))

            # Handle natural language commands
            else:
                try:
                    # Include context in the prompt
                    enhanced_prompt = f"""Context:
                    Current file: {context.get('current_file', 'None')}
                    Current directory: {context.get('current_dir', 'None')}

                    User request: {line}"""

                    messages = self.prompt.format_messages(
                        tool_descriptions=self.tool_descriptions,
                        user_input=enhanced_prompt
                    )

                    response = self.llm.invoke(messages)

                    # Parse the LLM response into tools
                    try:
                        import json
                        tools_data = json.loads(response.content)
                        for tool_data in tools_data:
                            parsed_command = ParsedCommand(
                                tool_name=tool_data["tool_name"],
                                tool_args=tool_data["tool_args"]
                            )
                            all_tools.append(parsed_command)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.error(f"Error parsing LLM response: {e}")
                        all_tools.append(ParsedCommand(
                            tool_name="conversation_response",
                            tool_args={"user_input": "Failed to parse the command. Please try again."}
                        ))

                except Exception as e:
                    logger.error(f"Error processing line: {e}")
                    all_tools.append(ParsedCommand(
                        tool_name="conversation_response",
                        tool_args={"user_input": str(e)}
                    ))

        return ParsedCommandList(tools=all_tools)

    def update_state_with_commands(self, state: Union[GraphState, ReactGraphState], commands: ParsedCommandList) -> Union[GraphState, ReactGraphState]:
        """Update the state with the parsed commands"""
        state["current_action_list"] = commands.tools
        if commands.tools:
            state["action_input"] = commands.tools[0].tool_args
            if isinstance(state, ReactGraphState):
                state["last_action"] = commands.tools[0]
        return state

    async def process_input(self, state: Union[GraphState, ReactGraphState]) -> Union[GraphState, ReactGraphState]:
        """Process the current input and update the state"""
        commands = self.parse_command(state)
        return self.update_state_with_commands(state, commands)
