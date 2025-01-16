from typing import List, Dict, TypedDict, Optional, Callable, Any
from pydantic import SecretStr
from langgraph.graph import StateGraph, START, END
import os
import json
import subprocess
import shlex
import re
from langchain.agents import Tool
from langchain_groq import ChatGroq
from dotenv import load_dotenv
from command_parser import CommandParser
from langchain.prompts import ChatPromptTemplate
import threading
import logging
from shelly_types.types import GraphState
from textual.widgets import RichLog
from textual_components.token_usage_logger import TokenUsagePlot



load_dotenv()

logging.basicConfig(level=logging.ERROR)

class Zap:
    state: GraphState
    output_log: RichLog
    token_usage_log: TokenUsagePlot
    def __init__(self):
        self.graph = self.setup_graph()
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.versatile_llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None)
        self.tools = {
            "debug_code": Tool(
                name="debug_code",
                func=self.debug_code,
                description="Debug the given code"
            ),
            "conversation_response": Tool(
                name="conversational_response",
                func=self.conversational_response,
                description="Respond to the user input"
            ),
            "run_code": Tool(
                name="run_code",
                func=self.run_code,
                description="Run a standalone file"
            ),
            "fix_code": Tool(
                name="fix_code",
                func=self.fix_code,
                description="Fix code with or without context"
            )
        }
        self.command_parser = CommandParser(self.tools)
        self.bug_fixer_prompt = ChatPromptTemplate(
            [
                ("system", """You are a highly specialized code debugger, whose sole job is to explain the error with faulty code.
                    There may be additional context provided, in which case use it to figure out the issue. Format the response with '\n' and '\t' as needed.
                    Provide an explanation for the response, as well as the corrected code afterward. """),
                ("user", "Context: {context}"),
                ("user", "Code: {code}")
            ]
        )
        self.state = GraphState(
            messages=[],
            tools=self.tools,
            current_input="",
            action_input={},
            action_output="",
            current_action_list=[],
            tool_history=[],
            context_summary="",
            last_tool_invoked=None,
            should_end=False
        )


    def clean_json_string(self, content: str) -> str:
        # Remove actual newlines and normalize escape sequences
        content = content.replace('\n', '\\n').replace('\r', '')
        # Clean up any double escaped newlines
        content = content.replace('\\\\n', '\\n')
        # Remove any invalid control characters
        content = re.sub(r'[\x00-\x1F\x7F]', '', content)
        return content

    def setup_graph(self):
        workflow = StateGraph(GraphState)

        workflow.add_node("parse_message", self.parse_message)
        workflow.add_node("execute_action", self.execute_action)

        workflow.add_edge(START, "parse_message")
        workflow.add_edge("parse_message", "execute_action")
        workflow.add_edge("execute_action", END)

        return workflow.compile()

    def parse_message(self, state: GraphState):
        print(f'parse_message: {state["messages"]}')
        # Handle multiline input properly
        user_input = state["messages"][-1]["content"]
        parsed_command = self.command_parser.parse_command(user_input)
        print(parsed_command)
        return {
            "current_action_list": parsed_command.tools  # constantly replace current_action_list, resetting after the actions are performed
        }

    def execute_action(self, state: GraphState):
        #last_response = state["messages"][-1]
        try:
            for action_to_take in state["current_action_list"]:
                # Store the action in state before executing
                state["action_input"] = action_to_take
                self.output_log.write("*"*200)
                self.output_log.write("shelly>")
                # Execute tool and capture returned state"
                if action_to_take.tool_name == "conversational_response":
                    state = self.conversational_response(state)
                elif action_to_take.tool_name == "run_code":
                    state = self.run_code(state)
                elif action_to_take.tool_name== "fix_code":
                    state = self.fix_code(state)

                # Verify state update
                if "action_output" in state:
                    self.output_log.write(f'\n{state["action_output"]}')
                else:
                    self.output_log.write('\nWarning: There was no output.')
                self.output_log.write("*"*200)
            return state

        except Exception as e:
            import traceback
            self.output_log.write(f'\nError in execute_action: {str(e)}')
            self.output_log.write(f'\n{traceback.format_exc()}')
            return state


    #======= TOOLS DEFINED HERE ================================================================#
    def debug_code(self, state: GraphState):
        print(f'debug code: {state["messages"]}')

    def conversational_response(self, state: GraphState):
        print(f'conversational_response: {state["messages"]}')
        #last_response = state["messages"][-1]
        try:
        #last_response_content = json.loads(last_response["content"].replace("'", '"'))
            action_input = state["action_input"]
            customized_prompt = ChatPromptTemplate([
                ("system", """You are a professional and specialized expert in computer programming. Your job is to respond to the user
                    in a explanatory and concise manner."""),
                ("user", "{session_context}"),
                ("user", "{user_input}")
            ])
            context = state["messages"] # might have to implement context selection or context summarization
            user_input = ""
            if isinstance(action_input, dict) and "user_input" in action_input["tool_args"]:
                user_input = action_input["tool_args"]["user_input"]
            elif isinstance(action_input, dict) and "input" in action_input["tool_args"]:
                user_input = action_input["tool_args"]["input"]
            formatted_customized_prompt = customized_prompt.format_messages(
                session_context=context, # the context from the session
                user_input = user_input
            )
            response = self.versatile_llm.invoke(formatted_customized_prompt)
            state = self.action_output_helper(state, response)
            input_tokens, output_tokens = self.log_token_usage(response)
            self.update_token_usage(input_tokens, output_tokens)
            return state
        except Exception as e:
            self.output_log.write("There was an issue processing your request. Please try again.")
            return state


    # it returns a file path ie: main.py-> need to convert to python3 main.py for subprocess.run to work
    def run_code(self, state: GraphState):
        #last_response = state["messages"][-1]
        #last_response_content = json.loads(last_response["content"].replace("'",'"'))
        last_response_content = state["action_input"]
        try:
            program_path = last_response_content.tool_args.path
            if not program_path:
                raise FileNotFoundError("No program path found")
           #result = subprocess.run(os.path.join(os.getcwd(), program_path), capture_output=True, check=True, text=True)
            process = subprocess.Popen(shlex.split(program_path),stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True, bufsize=1)

            def read_output(pipe, lines):
                for line in pipe:
                    line = line.strip()
                    lines.append(line)

            stdout, stderr = [], []

            stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout))
            stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr))

            stdout_thread.start()
            stderr_thread.start()

            stdout_thread.join()
            stderr_thread.join()

            return_code = process.wait()
            state = self.action_output_helper(state, str({"output": stdout}))
            return state
        except FileNotFoundError as e:
            print(str(e))
            state = self.action_output_helper(state, "The file wasn't found")
            return state
        except subprocess.CalledProcessError as error:
            traceback: str = error.stderr if error.stderr else str(error)
            error_information: str = str(error)
            state = self.action_output_helper(state, str({"traceback": traceback, "error_information": error_information}))
            return state
        except Exception as e:
            state = self.action_output_helper(state, str(e))
            return state

    def fix_code(self, state: GraphState):
        #last_response = state["messages"][-1]
        #last_response_content = json.loads(self.clean_json_string(last_response["content"]))
        last_response_content = state["action_input"]
        user_input, context = last_response_content["tool_args"]["code"], last_response_content["tool_args"]["context"] if "context" in last_response_content["tool_args"] else ""
        parameterized_bug_fixer_prompt = self.bug_fixer_prompt.format_messages(
            context = context,
            code = user_input
        )
        response = self.versatile_llm.invoke(parameterized_bug_fixer_prompt)
        state = self.action_output_helper(state, response)
        return state

    def write_code(self, state: GraphState):
        #last_response = state["messages"][-1]
        #last_response_content = json.loads(last_response["content"].replace("'", '"'))
        last_response_content = state["action_input"]


    #======= TOOLS DEFINED HERE ==============================================================#

    def action_output_helper(self, state: GraphState, llm_response):
        try:
            # Convert llm_response to string content
            if isinstance(llm_response, list):
                response_content = llm_response[0].content if llm_response else ""
            elif hasattr(llm_response, 'content'):
                response_content = llm_response.content
            else:
                response_content = str(llm_response)

            # Debug logging
            print(f"Debug: Processing response content: {response_content[:100]}...")
            # Update state
            state["action_output"] = response_content
            state["messages"] = state["messages"] + [{"role": "assistant", "content": response_content}]

            return state

        except Exception as e:
            import traceback
            error_msg = f"\nError in action_output_helper: {str(e)}\n{traceback.format_exc()}"
            if self.output_log:
                self.output_log.write(error_msg)
            else:
                print(error_msg)
            return state

    def log_token_usage(self, response):
        input_tokens = 0
        output_tokens = 0
        total_tokens = 0

        # Access the underlying response object for usage info
        if hasattr(response, 'additional_kwargs') and '_response' in response.additional_kwargs:
            raw_response = response.additional_kwargs['_response']
            if hasattr(raw_response, 'usage'):
                input_tokens = raw_response.usage.prompt_tokens
                output_tokens = raw_response.usage.completion_tokens
        return input_tokens, output_tokens

    def update_token_usage(self, input_tokens: int, output_tokens: int) -> None:
        """Safely update token usage if the logger is available"""
        if hasattr(self, 'token_usage_log') and self.token_usage_log is not None:
            self.token_usage_log.update_chart(input_tokens, output_tokens)



def main():
    output_log = RichLog()
    zap = Zap()
    zap.output_log = output_log
    #zap.state["messages"] = [{"role": "user", "content": "what is a binary tree"}]
    #zap.state["messages"] = [{"role": "user", "content": "execute ./test/test.js"}]

    zap.state["messages"] = [{"role": "user", "content": """fix this code:
        def calculate_average(numbers):
            total = 0
            count = 0
            while count < len(numbers):
                count + 1
                total = total + numbers[count]
            return total / count

            and then run test.py for me"""}]
    #for event in zap.graph.stream(zap.state):
     #   for value in event.values():
      #      print(value)
    zap.graph.invoke(zap.state)
    #print(zap.state["action_output"])


main()
