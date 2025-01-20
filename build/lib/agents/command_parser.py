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

        User: "/file test.py
        explain this code and fix any bugs"
        Assistant: [
            {
                "tool_name": "load_file",
                "tool_args": {"file_path": "test.py"}
            },
            {
                "tool_name": "explain_code",
                "tool_args": {
                    "code_source": "test.py",
                    "detail_level": "high"
                }
            },
            {
                "tool_name": "fix_code",
                "tool_args": {
                    "code_source": "test.py"
                }
            }
        ]

        User: "/file test.py
        what does this code do?"
        Assistant: [
            {
                "tool_name": "load_file",
                "tool_args": {"file_path": "test.py"}
            },
            {
                "tool_name": "explain_code",
                "tool_args": {
                    "code": "",  # Will be filled from loaded file
                    "detail_level": "high"
                }
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
        lines = user_input.strip().split('\n')
        all_tools = []
        context = {}  # Store context between lines

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Handle slash commands
            if line.startswith('/file '):
                file_path = line.split('/file ', 1)[1].strip()
                context['current_file'] = file_path
                all_tools.append(ParsedCommand(
                    tool_name="load_file",
                    tool_args={"file_path": file_path}
                ))
            elif line.startswith('/dir '):
                dir_path = line.split('/dir ', 1)[1].strip()
                context['current_dir'] = dir_path
                all_tools.append(ParsedCommand(
                    tool_name="load_directory",
                    tool_args={"directory_path": dir_path}
                ))
            else:
                # Process non-command lines through LLM with context
                try:
                    # Include context in the prompt
                    enhanced_prompt = f"""Context:
                    Current file: {context.get('current_file', 'None')}
                    Current directory: {context.get('current_dir', 'None')}

                    User request: {line}"""

                    formatted_prompt = self.prompt.format_messages(
                        tool_descriptions=self.tool_descriptions,
                        cached_examples=self.get_cached_examples(),
                        user_input=enhanced_prompt
                    )
                    response = self.llm.invoke(formatted_prompt)

                    if isinstance(response, dict):
                        tools = response.get('tools', [])
                    elif hasattr(response, 'tools'):
                        tools = response.tools
                    else:
                        tools = []

                    # For code-related tools, just set minimum required args
                    for tool in tools:
                        if tool.tool_name in ['explain_code', 'fix_code', 'analyze_code']:
                            tool.tool_args = {
                                'code': '',  # Empty string - tool will get content from messages
                                'detail_level': 'high' if tool.tool_name == 'explain_code' else None,
                                'analysis_type': 'general' if tool.tool_name == 'analyze_code' else None
                            }
                            # Remove None values
                            tool.tool_args = {k: v for k, v in tool.tool_args.items() if v is not None}

                    all_tools.extend(tools)

                except Exception as e:
                    print(f"Error processing line: {line}, error: {str(e)}")
                    all_tools.append(ParsedCommand(
                        tool_name="conversation_response",
                        tool_args={"user_input": line}
                    ))

        return ParsedCommandList(tools=all_tools)


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
