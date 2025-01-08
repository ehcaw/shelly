from typing import TypedDict, List, Optional, Union, Dict, Any
from langchain.prompts import ChatPromptTemplate
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
        self.available_tools = available_tools

        self.tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in available_tools
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
                    ("system", """You are a command parser for an AI assistant. Your job is to analyze user input and determine which tool to handle the input with. There is a tool to handle the case
                        where you should respond as if it was a conversation.

        Available tools:
        {tool_descriptions}

        Rules:
        1. If the user's request matches a tool's functionality, specify the tool_name and tool_args
        2. If the request is a general question or conversation, specify the tool name to be "conversation_response" and pass the user input as args
        3. Always respond in valid JSON format matching the example structure
        4. Tool arguments should be relevant to the tool's purpose
        5. Be precise in tool selection - only use a tool if the request clearly matches its purpose

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
        # Format the prompt with our tool descriptions and user input
        formatted_prompt = self.prompt.format_messages(
            tool_descriptions=self.tool_descriptions,
            examples=self.examples,
            user_input=user_input
        )

        # Get LLM response
        response: BaseMessage = await self.llm.ainvoke(formatted_prompt)

        # Extract the content from the BaseMessage object
        response_content = response.content if hasattr(response, 'content') else str(response)

        # Ensure response_content is a string
        if isinstance(response_content, str):
            parsed_response = json.loads(response_content)
        else:
            raise ValueError("Response content is not a valid JSON string")

        if not isinstance(parsed_response, dict):
            raise ValueError("Parsed response is not a dictionary")

        # Ensure the parsed response matches the structure of ParsedCommand
        return ParsedCommand(
            tool_name=parsed_response.get("tool_name"),
            tool_args=parsed_response.get("tool_args"),
        )
