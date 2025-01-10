from typing import TypedDict, List, Optional, Union, Dict, Any
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers.list import T
from langchain_groq import ChatGroq
from langchain.schema import BaseMessage
from pydantic import SecretStr
from langchain.tools import Tool
import os
import json
from dotenv import load_dotenv

load_dotenv()

class ParsedCommand(TypedDict):
    tool_name: Optional[str]
    tool_args: Optional[dict]

class CommandParser:
    def __init__(self, available_tools: Dict[str, Tool]):
        self.available_tools = available_tools.items()

        self.tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in list(available_tools.values())
        ])

        # Few-shot examples to help the llm classify actions to do
        self.examples = """
        Examples:
        User: "Can you help me debug this code: def hello(): print('hi')"
        Assistant: {
            "tool_name": "debug_code",
            "tool_args": {"code": "def hello(): print('hi')"},
        }

        User: "Write me a function that calculates fibonacci numbers"
        Assistant: {
            "tool_name": "write_code",
            "tool_args": {"spec": "Write a function that calculates fibonacci numbers"},
        }
        User: "What's the best way to learn Python?"
        Assistant: {
            "tool_name": "conversational_response",
            "tool_args": {"user_input": "What is the best way to learn python"},
        }
        User: "Run the script located at /path/to/script.py"
        Assistant: {
            "tool_name": "run_code",
            "tool_args": {"path": "python3 /path/to/script.py"},
        }
        User: "How do I install packages using pip?"
        Assistant: {
            "tool_name": "conversational_response",
            "tool_args": {"user_input": "How do I install packages using pip"},
        }
        User: "Execute the file main.py in the current directory"
        Assistant: {
            "tool_name": "run_code",
            "tool_args": {"path": "python3 main.py"},
        }

        User: "Start a terminal session to monitor logs"
        Assistant: {
            "tool_name": "open_terminal",
            "tool_args": {},
        }

        User: "Fix this code: def hello():
            print('what the bruh"
        Assistant: {
            "code": "def hello():
                print('what the bruh"
            "context": ""
        }
        """

        self.prompt = ChatPromptTemplate.from_messages([
            ("system", r'You are a command parser. Return ONLY a JSON object with this structure:{{"tool_name": "<tool name>","tool_args": {{"state": {{}}, // other args as needed}}}}'),
            ("system", """Available tools: {tool_descriptions}"""),
            ("system", """{examples}"""),
            ("user", "{user_input}")
        ])
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.llm = ChatGroq(
                model="llama-3.2-3b-preview",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)

    def parse_command(self, user_input: str) -> ParsedCommand:
        """Parse user input to determine if it should use a tool or conversational response"""
        try:
            # Format the prompt with our tool descriptions and user input
            formatted_prompt = self.prompt.format_messages(
                tool_descriptions=self.tool_descriptions,
                examples=self.examples,
                user_input=user_input
            )

            # Add debugging

            # Get LLM response
            response: BaseMessage = self.llm.invoke(formatted_prompt)


            # Extract content
            if isinstance(response, list):
                response_content = response[0] if response else ""
            elif hasattr(response, 'content'):
                response_content = response.content
            else:
                response_content = str(response)

            # Clean up the response
            response_content = str(response_content).strip()

            # Try to find valid JSON in the response
            start = response_content.find('{')
            end = response_content.rfind('}')

            if start != -1 and end != -1:
                json_str = response_content[start:end+1]
                print("Extracted JSON string:", json_str)
                parsed_response = json.loads(json_str)
            else:
                raise json.JSONDecodeError("No JSON object found", response_content, 0)


            # Validate the response structure
            if not isinstance(parsed_response, dict):
                raise ValueError(f"Expected dict, got {type(parsed_response)}")

            tool_name = parsed_response.get("tool_name")
            tool_args = parsed_response.get("tool_args", {})

            # Validate and ensure proper tool selection
            if not tool_name:
                return ParsedCommand(
                    tool_name="conversational_response",
                    tool_args={"input": user_input, "state": {}}
                )

            # For conversational responses, ensure proper format
            if tool_name == "conversational_response":
                return ParsedCommand(
                    tool_name="conversational_response",
                    tool_args={"input": user_input, "state": {}}
                )

            # Check if tool name is in available tools
            available_tool_names = [tool[0] for tool in self.available_tools]
            if tool_name in available_tool_names:
                # Ensure state is present
                if "state" not in tool_args:
                    tool_args["state"] = {}

                # Special handling for run_code
                if tool_name == "run_code":
                    tool_args.setdefault("spec", "")
                    tool_args.setdefault("path", "")

                # Special handling for debug_code
                if tool_name == "debug_code":
                    tool_args.setdefault("code", user_input)

                # Special handling for write_code
                if tool_name == "write_code":
                    tool_args.setdefault("spec", user_input)

                return ParsedCommand(
                    tool_name=str(tool_name),
                    tool_args=tool_args
                )

            # If tool_name is invalid, default to conversation
            return ParsedCommand(
                tool_name="conversational_response",
                tool_args={"input": user_input, "state": {}}
            )

        except Exception as e:
            print(f"Error in parse_command: {str(e)}")
            # Default to conversation on error
            return ParsedCommand(
                tool_name="conversational_response",
                tool_args={"input": user_input, "state": {}}
            )

def debug_code():
    print('debug')

def conversational_response():
    print('conversation')

def run_code():
    print('run code')
