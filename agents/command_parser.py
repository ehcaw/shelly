from typing import TypedDict, List, Optional, Union, Dict, Any
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers.list import T
from langchain_groq import ChatGroq
from langchain.schema import BaseMessage
from pydantic import SecretStr
from langchain.tools import Tool
import os
import json

class ParsedCommand(TypedDict):
    tool_name: Optional[str]
    tool_args: Optional[dict]

class CommandParser:
    def __init__(self, available_tools: List[Tool]):
        self.available_tools = [{
            "name": tool.name,
            "description": tool.description
        } for tool in available_tools]

        self.tool_descriptions = "\n".join([
            f"- {tool['name']}: {tool['description']}"
            for tool in self.available_tools
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
            "tool_args": {"path": "/path/to/script.py"},
        }

        User: "Open a new terminal session for monitoring"
        Assistant: {
            "tool_name": "open_terminal",
            "tool_args": {},
        }

        User: "Can you debug this function? def add(a, b): return a + b"
        Assistant: {
            "tool_name": "debug_code",
            "tool_args": {"code": "def add(a, b): return a + b"},
        }

        User: "Generate a Python class for a simple calculator"
        Assistant: {
            "tool_name": "write_code",
            "tool_args": {"spec": "Generate a Python class for a simple calculator"},
        }

        User: "How do I install packages using pip?"
        Assistant: {
            "tool_name": "conversational_response",
            "tool_args": {"user_input": "How do I install packages using pip"},
        }

        User: "Execute the file main.py in the current directory"
        Assistant: {
            "tool_name": "run_code",
            "tool_args": {"path": "./main.py"},
        }

        User: "Start a terminal session to monitor logs"
        Assistant: {
            "tool_name": "open_terminal",
            "tool_args": {},
        }

        User: "Help me debug this error: def divide(a, b): return a / b"
        Assistant: {
            "tool_name": "debug_code",
            "tool_args": {"code": "def divide(a, b): return a / b"},
        }

        User: "Write a function to sort a list of numbers"
        Assistant: {
            "tool_name": "write_code",
            "tool_args": {"spec": "Write a function to sort a list of numbers"},
        }

        User: "What are the best practices for writing clean code?"
        Assistant: {
            "tool_name": "conversational_response",
            "tool_args": {"user_input": "What are the best practices for writing clean code"},
        }

        User: "Run the test suite located at /tests"
        Assistant: {
            "tool_name": "run_code",
            "tool_args": {"path": "/tests"},
        }

        User: "Open a terminal to run live commands"
        Assistant: {
            "tool_name": "open_terminal",
            "tool_args": {},
        }
        """

        self.prompt = ChatPromptTemplate.from_messages([
                    ("system", """You are a command parser that must return VALID JSON matching this exact structure:
                        {
                            "tool_name": "<exact tool name>",
                            "tool_args": {
                                // tool specific arguments
                                "state": {}
                            }
                        }

        Available tools and their exact names:
        {tool_descriptions}

        Rules:
        1. You MUST use EXACT tool names as listed above
        2. Tool arguments must match exactly what the tool expects
        3. For general questions or conversation, use "conversational_response"
        4. Response must be valid JSON matching the example structure
        5. Always include "state" in tool_args
        6. For run_code, include both "state" and "spec" in tool_args
        7. For general questions use:
           {
               "tool_name": "conversational_response",
               "tool_args": {
                   "input": "<user's message>",
                   "state": {}
               }
           }
        8. For code debugging use:
           {
               "tool_name": "debug_code",
               "tool_args": {
                   "code": "<code to debug>",
                   "state": {}
               }
           }

        {examples}
        """),
            ("user", "{user_input}")
        ])

        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.llm = ChatGroq(
                model="llama3-8b-8192",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)

    async def parse_command(self, user_input: str) -> ParsedCommand:
        """Parse user input to determine if it should use a tool or conversational response"""
        try:
            # Format the prompt with our tool descriptions and user input
            formatted_prompt = self.prompt.format_messages(
                tool_descriptions=self.tool_descriptions,
                examples=self.examples,
                user_input=user_input
            )

            # Add debugging
            print("Sending prompt to LLM:", formatted_prompt)

            # Get LLM response
            response: BaseMessage = await self.llm.ainvoke(formatted_prompt)

            # Debug raw response
            print("Raw LLM response:", response)

            # Extract content and ensure it's a string
            response_content = response.content if hasattr(response, 'content') else str(response)
            print("Response content:", response_content)

            # Parse JSON carefully
            try:
                parsed_response = json.loads(str(response_content))
            except json.JSONDecodeError as e:
                print(f"JSON parsing error: {e}")
                # Default to conversation if parsing fails
                return ParsedCommand(
                    tool_name="conversational_response",
                    tool_args={"input": user_input, "state": {}}
                )

            print("Parsed response:", parsed_response)

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

            # For other tools, ensure proper args structure
            if tool_name in self.available_tools:
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
            else:
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
