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
from agents.command_parser import CommandParser
from langchain.prompts import ChatPromptTemplate
import threading
import logging
from shelly_types.types import GraphState
from textual.widgets import RichLog
from typing import Optional


load_dotenv()

logging.basicConfig(level=logging.ERROR)



class Zap:
    state: GraphState
    output_log: RichLog
    def __init__(self, output_log: Optional[RichLog]):
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
        workflow.add_node("update_state", self.update_state)

        workflow.add_edge(START, "parse_message")
        workflow.add_edge("parse_message", "execute_action")
        workflow.add_edge("execute_action", "update_state")
        workflow.add_edge("update_state", END)

        return workflow.compile()

    def parse_message(self, state: GraphState):
        print(f'parse_message: {state["messages"]}')
        # Handle multiline input properly
        user_input = state["messages"][-1]["content"]
        parsed_command = self.command_parser.parse_command(user_input)


        '''return {
            "messages": state["messages"] + [
                {"role": "assistant", "content": parsed_command}
            ]
        }'''
        print(f"parsed command: {parsed_command}")
        return {
            "current_action_list": parsed_command
        }

    def execute_action(self, state: GraphState):

        last_response = state["messages"][-1]

        try:
            last_response_content = last_response["content"]
            if not last_response_content or len(last_response_content) == 0:
                print("Content is empty")
                return
            #last_response_content = json.loads(last_response_content)
            # content is a list of tools for the graph to execute
            '''
            for step in last_response_content:
                print(step)
                #step = json.loads(str(step).replace("'",'"'))

                if step["tool_name"] == "conversational_response":
                    state = self.conversational_response(state)
                if step["tool_name"] == "run_code":
                    state = self.run_code(state)
                if step["tool_name"] == "fix_code":
                    state = self.fix_code(state)
                '''
            for action_to_take in state["current_action_list"]:
                state["action_input"] = dict(action_to_take)
                if action_to_take["tool_name"] == "conversational_response":
                    state = self.conversational_response(state)
                if action_to_take["tool_name"] == "run_code":
                    state = self.run_code(state)
                if action_to_take["tool_name"] == "fix_code":
                    state = self.fix_code(state)
                #self.output_log.write(f"\n: Assistant: {state["action_output"]}")
                print(f"\nAssistant: {state["action_output"]}")
            return state

        except json.JSONDecodeError as e:
            print(f"JSON Decode Error: {e}")
            print(f"Failed to parse content: {last_response_content}")
        except Exception as e:
            print(f"Other error: {type(e)}: {e}")

    def update_state(self, state: GraphState):
        self.state = state
        return state

    #======= TOOLS DEFINED HERE ================================================================#
    def debug_code(self, state: GraphState):
        print(f'debug code: {state["messages"]}')

    def conversational_response(self, state: GraphState):
        print(f'conversational_response: {state["messages"]}')
        #last_response = state["messages"][-1]

        #last_response_content = json.loads(last_response["content"].replace("'", '"'))
        last_response_content = state["action_input"]
        customized_prompt = ChatPromptTemplate([
            ("system", """You are a professional and specialized expert in computer programming. Your job is to respond to the user
                in a explanatory and concise manner."""),
            ("user", "{session_context}"),
            ("user", "{user_input}")
        ])
        context = state["messages"] # might have to implement context selection or context summarization
        formatted_customized_prompt = customized_prompt.format_messages(
            session_context=context, # the context from the session
            user_input = last_response_content["tool_args"]["input"]
        )
        response = self.versatile_llm.invoke(formatted_customized_prompt)
        state = self.action_output_helper(state, response)
        return state


    # it returns a file path ie: main.py-> need to convert to python3 main.py for subprocess.run to work
    def run_code(self, state: GraphState):
        #last_response = state["messages"][-1]
        #last_response_content = json.loads(last_response["content"].replace("'",'"'))
        last_response_content = state["action_input"]
        try:
            program_path = last_response_content["tool_args"]["path"]
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
        print(f"last response contnet: {last_response_content}")
        print(f"type of last response: {type(last_response_content)}")
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
        if isinstance(llm_response, list):
            response_content = llm_response[0].content if llm_response else ""
        elif hasattr(llm_response, 'content'):
            response_content = llm_response.content
        else:
            response_content = str(llm_response)

        # Update state with the response
        print(f"response contnet: {response_content}")
        state["action_output"] = response_content
        state["messages"] = state["messages"] + [{"role": "assistant", "content": response_content}]
        return state

def main():
    zap = Zap(output_log=None)
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
    '''
    for event in zap.graph.stream(zap.state):
        for value in event.values():
            print(value)
    '''
    zap.graph.invoke(zap.state)
    print(zap.state["action_output"])


main()
