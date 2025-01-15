from typing import Dict, Union, List, Dict, Any, Optional
from pydantic import BaseModel, SecretStr
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages.ai import AIMessage
from langchain_groq import ChatGroq
from langchain.tools import Tool
import os
from dotenv import load_dotenv
import sys
from shelly_types.types import ParsedCommand, ParsedCommandList, UsageInfo, LLMResponse
from functools import lru_cache
from langchain_community.cache import InMemoryCache
from langchain.globals import set_llm_cache

load_dotenv()



class CommandParser:
    def __init__(self, available_tools: Dict[str, Tool]):
        self.available_tools = available_tools.items()

        self.tool_descriptions = "\n".join([
            f"- {tool.name}: {tool.description}"
            for tool in list(available_tools.values())
        ])

        set_llm_cache(InMemoryCache())


        # Few-shot examples to help the llm classify actions to do
        self.examples = """
        Examples:
        User: "Can you help me debug this code: def hello(): print('hi')"
        Assistant: [
            {
                "tool_name": "debug_code",
                "tool_args": {"code": "def hello(): print('hi')"}
            }
        ]

        User: "Write me a function that calculates fibonacci numbers"
        Assistant: [
            {
                "tool_name": "write_code",
                "tool_args": {"spec": "Write a function that calculates fibonacci numbers"}
            }
        ]

        User: "What's the best way to learn Python?"
        Assistant: [
            {
                "tool_name": "conversational_response",
                "tool_args": {"user_input": "What is the best way to learn python"}
            }
        ]

        User: "Run the script located at /path/to/script.py"
        Assistant: [
            {
                "tool_name": "run_code",
                "tool_args": {"path": "python3 /path/to/script.py"}
            }
        ]

        User: "How do I install packages using pip?"
        Assistant: [
            {
                "tool_name": "conversational_response",
                "tool_args": {"user_input": "How do I install packages using pip"}
            }
        ]

        User: "Execute the file main.py in the current directory"
        Assistant: [
            {
                "tool_name": "run_code",
                "tool_args": {"path": "python3 main.py"}
            }
        ]

        User: "Start a terminal session to monitor logs"
        Assistant: [
            {
                "tool_name": "open_terminal",
                "tool_args": {}
            }
        ]

        User: "Fix this code: def hello():
            print('what the bruh"
        Assistant: [
            {
                "tool_name": "fix_code",
                "tool_args": {"code": "def hello(): print('what the bruh"}
            }
        ]

        User: "Write a function to calculate factorial and then run it"
        Assistant: [
            {
                "tool_name": "write_code",
                "tool_args": {"spec": "Write a function to calculate factorial"}
            },
            {
                "tool_name": "run_code",
                "tool_args": {"path": "python3 factorial.py"}
            }
        ]

        User: "Debug this code and then run it: def hello(): print('hi')"
        Assistant: [
            {
                "tool_name": "debug_code",
                "tool_args": {"code": "def hello(): print('hi')"}
            },
            {
                "tool_name": "run_code",
                "tool_args": {"path": "python3 hello.py"}
            }
        ]

        User: "Explain what a binary tree is and then write a function to create one"
        Assistant: [
            {
                "tool_name": "conversational_response",
                "tool_args": {"user_input": "Explain what a binary tree is"}
            },
            {
                "tool_name": "write_code",
                "tool_args": {"spec": "Write a function to create a binary tree"}
            }
        ]
        """
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a command parser that converts user input into tool calls.
                Available tools:
                {tool_descriptions}

                Use these examples as reference for similar cases:
                {cached_examples}

                Return ONLY a JSON array of tool objects."""),
            ("user", "{user_input}")
        ])

        self.cached_examples = self.examples

        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.llm = ChatGroq(
                model="llama-3.2-3b-preview",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None).with_structured_output(ParsedCommandList)

    @lru_cache(maxsize=1)  # Cache the formatted examples
    def get_cached_examples(self):
        return self.cached_examples



    def parse_command(self, user_input: str) -> ParsedCommandList:
        try:
            formatted_prompt = self.prompt.format_messages(
                tool_descriptions=self.tool_descriptions,
                examples=self.get_cached_examples(),
                user_input=user_input
            )

            # Get LLM response
            response = self.llm.invoke(formatted_prompt)

            # Extract usage information from the response
            input_tokens = 0
            output_tokens = 0
            total_tokens = 0

            # Access the underlying response object for usage info

            # Handle the response based on its type
            if isinstance(response, dict):
                tools = response.get('tools', [])
            elif hasattr(response, 'tools'):
                tools = response.tools
            else:
                tools = []

            return ParsedCommandList(
                tools=tools,
            )

        except Exception as e:
            print(f"Error in parse_command: {str(e)}")
            # Default to conversation on error
            return ParsedCommandList(
                tools=[ParsedCommand(
                    tool_name = "conversational_response",
                    tool_args={"input": user_input}
                )],
            )


def debug_code():
    print('debug')

def conversational_response():
    print("conversational")

def run_code():
    print("run")

def fix_code():
    print("fix code")

tools = {
    "debug_code": Tool(
        name="debug_code",
        func=debug_code,
        description="Debug the given code"
    ),
    "conversation_response": Tool(
        name="conversational_response",
        func=conversational_response,
        description="Respond to the user input"
    ),
    "run_code": Tool(
        name="run_code",
        func=run_code,
        description="Run a standalone file"
    ),
    "fix_code": Tool(
        name="fix_code",
        func=fix_code,
        description="Fix code with or without context"
    )
}

def main():
    parser = CommandParser(tools)
    print(parser.parse_command("execute test.py and explain what a binary tree is"))
