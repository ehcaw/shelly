import os
import sys
sys.path.append("..") # Adds higher directory to python modules path.
#sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from langchain import hub
from langchain_groq import ChatGroq
from langchain.agents import AgentExecutor, create_react_agent
from langgraph.graph import StateGraph, START, END
from langchain.agents import Tool
from langchain_community.tools.tavily_search import TavilySearchResults
from shelly_types.types import (ReactGraphState, FileInput, DirectoryInput, CodeInput, CodeRunInput, ConversationInput, CodeAnalysisInput,
    CodeFixInput, CodeWriteInput, CodeDebugInput, DocumentationSearchInput, ContextManagementInput, CodeExplanationInput, WriteMode, ParsedCommand, ParsedCommandList, CustomRichLog)
from shelly_types.utils import llm_response_helper
from textual_components.token_usage_logger import TokenUsagePlot
from agents.command_parser import CommandParser
from textual.widgets import RichLog
from langchain.prompts import ChatPromptTemplate
from pydantic import SecretStr, BaseModel, Field
from dotenv import load_dotenv
import subprocess
import threading
import shlex
import pathlib
from pathlib import Path
load_dotenv()

project_root = str(Path(__file__).parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

class Splatter:
    output_log: CustomRichLog
    state: ReactGraphState
    token_usage_log: TokenUsagePlot
    def __init__(self):
        self.graph = self.setup_graph()
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        self.versatile_llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key= SecretStr(api_key),
            temperature=0,
            stop_sequences=None)
        self.tools = {
            "analyze_code": Tool(
                name="analyze_code",
                func=self.analyze_code,
                description="Analyze code to understand its structure and potential issues",
                args_schema=CodeAnalysisInput
            ),
            '''
            "get_context": Tool(
                name="get_context",
                func=self.get_context,
                description="Get relevant context from previous interactions or file content",
                args_schema=ContextManagementInput
            ),
            '''
            "load_file": Tool(
                name="load_file",
                func=self.load_file,
                description="Read the contents of a file and load it into context",
                args_schema=FileInput
            ),
            "load_directory": Tool(
                name="load_directory",
                func=self.load_directory,
                description="Load all files from a directory",
                args_schema=DirectoryInput
            ),
            "run_code": Tool(
                name="run_code",
                func=self.run_code,
                description="Run a standalone file and get its output",
                args_schema=CodeRunInput
            ),
            "fix_code": Tool(
                name="fix_code",
                func=self.fix_code,
                description="Fix identified issues in the code",
                args_schema=CodeFixInput
            ),

            "write_code": Tool(
                name="write_code",
                func=self.write_code,
                description="Write or modify code in a file",
                args_schema=CodeWriteInput
            ),
            '''
            "debug_code": Tool(
                name="debug_code",
                func=self.debug_code,
                description="Run code in debug mode and analyze output",
                args_schema=CodeDebugInput
            ),
            '''
            "search_documentation": Tool(
                name="search_documentation",
                func=self.search_documentation,
                description="Search relevant documentation or examples",
                args_schema=DocumentationSearchInput
            ),
            '''
            "manage_context": Tool(
                name="manage_context",
                func=self.manage_context,
                description="Add, update, or clear context for the current session",
                args_schema=ContextManagementInput
            ),
            '''
            "explain_code": Tool(
                name="explain_code",
                func=self.explain_code,
                description="Provide detailed explanation of code functionality",
                args_schema=CodeExplanationInput
            ),
            "conversation_response": Tool(
                name="conversation_response",
                func=self.conversation_response,
                description="Respond to user questions or provide guidance",
                args_schema=ConversationInput
            )
        }
        self.command_parser = CommandParser(available_tools=self.tools)
        self.state = ReactGraphState(
            messages=[],
            tools=self.tools,
            current_input="",
            action_input={},
            action_output="",
            current_action_list=[],
            tool_history=[],
            should_end=False,
            last_action=None,
            observation=None,
            action_error=None
        )

    def setup_graph(self):
        workflow = StateGraph(ReactGraphState)

        # Add nodes for each step in the ReAct pattern
        workflow.add_node("reason", self.reason)      # Think about what to do
        workflow.add_node("action", self.action)      # Execute the chosen action
        workflow.add_node("observe", self.observe)    # Observe the results

        # Add edges to create the cycle
        workflow.add_edge(START, "reason")
        workflow.add_edge("reason", "action")
        workflow.add_edge("action", "observe")
        #workflow.add_edge("observe", "reason")  # Continue the cycle
        #orkflow.add_edge("observe", END)       # Or end if task is complete

        # Add conditional logic
        def should_continue(state: ReactGraphState) -> bool:
            should_continue = not state["should_end"] and len(state["current_action_list"]) > 0
            if self.output_log:
                self.output_log.write(f"Debug: should_continue = {should_continue}, should_end = {state['should_end']}, current_action_list = {len(state['current_action_list'])}\n")
            return should_continue

        # Define when to continue the cycle vs when to end
        workflow.add_conditional_edges(
            "observe",
            should_continue,
            {
                True: "reason",   # Continue the cycle
                False: END        # End if task is complete
            }
        )

        return workflow.compile()

    def reason(self, state: ReactGraphState) -> ReactGraphState:
        """Think about what action to take next"""
        if self.output_log:
            self.output_log.write(f"\nREASON STEP - current_input: {state['current_input']}")
            self.output_log.write(f"\nREASON STEP - messages: {state['messages']}")


        current_situation = state["current_input"]

        if current_situation is None or len(current_situation) == 0:
            if self.output_log:
                self.output_log.write("\nNo input to process, returning")
            return state
        # For simple questions, directly set up conversation response
        if not any(keyword in current_situation.lower() for keyword in ['code', 'file', 'directory', 'run', 'debug', 'fix']):
            command = ParsedCommand(
                tool_name="conversation_response",
                tool_args={"user_input": current_situation}
            )
            state["current_action_list"] = [command]
            state["action_input"] = {"user_input": current_situation}
            return state

        response = self.command_parser.parse_command(current_situation)

        # Parse the response to determine next action
        parsed_response = llm_response_helper(response)
        self.output_log.write(f'parsed response: {parsed_response} and {response}')
        state["current_action_list"] = response.tools
        state["current_input"] = ""

        # Logging
        if self.output_log:
            self.output_log.write(f"Debug: Reasoning response = {parsed_response}, current_action_list = {state['current_action_list']}\n")

        return state

    def action(self, state: ReactGraphState) -> ReactGraphState:
        """Execute the chosen action"""
        try:
            if len(state["current_action_list"]) == 0:
                if self.output_log:
                    self.output_log.write("No actions to execute")
                state["should_end"] = True
                return state

            current_action = state["current_action_list"].pop(0)
            if self.output_log:
                self.output_log.write(f"Executing action: {current_action.tool_name}")
                self.output_log.write(f"With args: {current_action.tool_args}")

            if current_action.tool_name in self.tools:
                state["action_input"] = current_action.tool_args
                tool_func = getattr(self, current_action.tool_name)
                state = tool_func(state)
                state["last_action"] = current_action  # Make sure this is set

                if self.output_log:
                    self.output_log.write(f"Action result: {state['action_output']}")

            return state
        except Exception as e:
            if self.output_log:
                self.output_log.write(f"Action failed: {str(e)}")
            state["action_error"] = str(e)
            return state

    def observe(self, state: ReactGraphState) -> ReactGraphState:
        """Observe and analyze the results of the action"""
        last_action: ParsedCommand = state["last_action"]
        action_output = state["action_output"]

        if len(state["current_action_list"]) > 0:
            state["should_end"] = False
            return state

        # If we just completed a conversation response, we can end
        if last_action and last_action.tool_name == "conversation_response":
            if action_output:  # Only end if we actually got a response
                state["should_end"] = True
                return state

        self.output_log.write(f'Observing after action: {last_action}')
        self.output_log.write(f'Action output: {action_output}')
        self.output_log.write(f'Remaining actions: {len(state["current_action_list"])}')

        # If we have more actions to execute, continue
        if len(state["current_action_list"]) > 0:
            state["should_end"] = False
            return state

        # If we just executed a command and got output, continue to process remaining actions
        if last_action and action_output:
            if not state["current_action_list"]:  # No more actions
                state["should_end"] = True
            return state

        # Create an observation prompt
        prompt = ChatPromptTemplate([
            ("system", """Analyze the results of the last action and determine if the task is complete
                         or if more actions are needed."""),
            ("user", """Last action: {action}
                       Result: {result}
                       Should we continue? If yes, what needs to be done next?""")
        ])

        response = self.versatile_llm.invoke(prompt.format(
            action=last_action,
            result=action_output
        ))

        # Update state based on observation
        response_content = llm_response_helper(response)
        state["observation"] = response_content

        # More robust check for task completion
        if "task complete" in response_content.lower() or "no further action" in response_content.lower():
            state["should_end"] = True
        else:
            state["should_end"] = False

        # Logging
        if self.output_log:
            self.output_log.write(f"Observation response: {response_content}\n")
            self.output_log.write(f"should_end set to: {state['should_end']}\n")

        return state

    def action_output_helper(self, state: ReactGraphState, llm_response):
        try:
            # Convert response to string content
            if isinstance(llm_response, list):
                response_content = llm_response[0].content if llm_response else ""
            elif hasattr(llm_response, 'content'):
                response_content = llm_response.content
            else:
                response_content = str(llm_response)

            # Update state
            state["action_output"] = response_content
            state["messages"].append({"role": "assistant", "content": response_content})

            # Only log if we have an output log
            if self.output_log:
                self.output_log.write(f'\nAction Output: {response_content}\n')
                self.output_log.write(f'\nMessages: {state["messages"]}')

            return state

        except Exception as e:
            error_msg = f"Error in output helper: {str(e)}"
            if self.output_log:
                self.output_log.write(f"\nERROR: {error_msg}\n")
            state["action_output"] = error_msg
            return state

    def handle_tool_error(self, state: ReactGraphState, error: Exception) -> ReactGraphState:
        error_message = f"Error: {str(error)}"
        state["action_output"] = error_message
        state["action_error"] = error_message
        return state

    def debug_log(self, message: str):
        """Helper to handle debug logging consistently"""
        if self.output_log:
            self.output_log.write(f"\nDEBUG: {message}\n")


    #TOOLS DEFINED HERE

    def run_code(self, state: ReactGraphState):
        #last_response = state["messages"][-1]
        #last_response_content = json.loads(last_response["content"].replace("'",'"'))
        #last_response_content = state["action_input"]
        try:
            input_args = CodeRunInput.model_validate(state["action_input"])
            cmd = [str(input_args.path)] + (input_args.args or [])
            process = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.PIPE,text=True, bufsize=1)
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
            return self.handle_tool_error(state, e)

    def conversation_response(self, state: ReactGraphState):
        try:
            action_input = ConversationInput.model_validate(state["action_input"])
            customized_prompt = ChatPromptTemplate([
                ("system", """You are an expert in computer programming and software development.
                    Provide clear, accurate, and helpful responses to questions.
                    If asked about programming concepts, include examples when relevant."""),
                ("user", "{user_input}")
            ])

            response = self.versatile_llm.invoke(customized_prompt.format(
                user_input=action_input.user_input
            ))

            state = self.action_output_helper(state, response)
            state["should_end"] = True  # Mark task as complete
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

    def load_file(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = FileInput.model_validate(state["action_input"])
            file_path = input_args.file_path

            # Convert string to Path if needed
            if isinstance(file_path, str):
                file_path = Path(file_path)

            # Try different possible locations
            possible_paths = [
                file_path,  # Try direct path first
                Path.cwd() / file_path,  # Try current working directory
                Path(__file__).parent / file_path,  # Try script's directory
                Path(__file__).parent.parent / file_path  # Try parent directory
            ]

            # Try each possible path
            for path in possible_paths:
                if path.exists():
                    file_contents = path.read_text()
                    state["messages"].append({"role": "user", "content": file_contents})
                    return self.action_output_helper(state,
                        f"Successfully loaded file {path}\nContents:\n{file_contents}")

            # If we get here, file wasn't found
            return self.action_output_helper(state,
                f"Error: File {file_path} not found. Searched in:\n" +
                "\n".join(str(p) for p in possible_paths))

        except Exception as e:
            return self.action_output_helper(state, f"Error loading file: {str(e)}")

    def load_directory(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = DirectoryInput.model_validate(state["action_input"])
            dir_path = input_args.directory_path
            if dir_path is None or not dir_path.is_dir():
                raise Exception("Directory provided isn't valid")
            for file in dir_path.iterdir():
                state["messages"] = state["messages"] + [{"role": "user", "content": file.read_text()}]
            state = self.action_output_helper(state, f'Successfully loaded files in {dir_path}')
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

    def analyze_code(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = CodeAnalysisInput.model_validate(state["action_input"])
            code_content = input_args.code if isinstance(input_args.code, str) else input_args.code.read_text()
            analysis_prompt = ChatPromptTemplate([
                ("system", """You are a professional and specialized expert in computer programming. Your job is to respond to the user
                    in a {analysis_type} manner"""),
                ("user", "{user_input}")
            ])

            response = self.versatile_llm.invoke(analysis_prompt.format_messages(
                analysis_type=input_args.analysis_type,
                user_input=code_content
            ))
            state = self.action_output_helper(state, response)
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

    def fix_code(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = CodeFixInput.model_validate(state["action_input"])
            code_content = input_args.code if isinstance(input_args.code, str) else input_args.code.read_text()
            issues = input_args.issues if input_args.issues is not None else []
            fix_prompt = ChatPromptTemplate([
                ("system", """You are a professional and specialized expert in computer programming. Your job is to fix this user's code
                    and explain why it was wrong."""),
                ("user", "{code_content}"),
                ("user", "{issues}")
            ])
            response = self.versatile_llm.invoke(fix_prompt.format_messages(
                code_content = code_content,
                issues = str(issues)
            ))
            state = self.action_output_helper(state, response)
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

    def write_code(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = CodeWriteInput.model_validate(state["action_input"])
            file_path, content, mode, line_modifications = input_args.file_path, input_args.content, input_args.mode, input_args.line_modifications

            if mode == WriteMode.OVERWRITE:
                file_path.write_text(content)

            elif mode == WriteMode.APPEND:
                with file_path.open('a') as f:
                    f.write(content)

            elif mode in (WriteMode.INSERT, WriteMode.MODIFY):
                if not line_modifications:
                    raise ValueError("There were no code modifications provided for INSERT/MODIFY mode")
                lines = file_path.read_text().splitlines()
                for mod in line_modifications:
                    if mode == WriteMode.INSERT:
                        lines.insert(mod.line_number, mod.content)
                    elif mode == WriteMode.MODIFY:
                        if 0 <= mod.line_number < len(lines):
                            lines[mod.line_number] = mod.content

                input_args.file_path.write_text('\n'.join(lines) + '\n')
            state = self.action_output_helper(state, f'Code changed in {file_path} using {mode}')
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

    def explain_code(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = CodeExplanationInput.model_validate(state["action_input"])

            # If code is empty, get it from the last loaded file
            if not input_args.code:
                # Get the last message which should be the file content
                if state["messages"] and state["messages"][-1]["content"]:
                    code_content = state["messages"][-1]["content"]
                else:
                    raise ValueError("No code content available")
            else:
                code_content = input_args.code
            detail_level = input_args.detail_level
            explanation_prompt = ChatPromptTemplate([
                ("system", """You are a professional and specialized expert in computer programming. Your job is to explain this code
                    segment with {detail_level} detail"""),
                ("user", "{code_content}"),
            ])
            response = self.versatile_llm.invoke(explanation_prompt.format_messages(
                detail_level = detail_level,
                code_content = code_content
            ))
            state = self.action_output_helper(state, response)
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

    def search_documentation(self, state: ReactGraphState) -> ReactGraphState:
        try:
            input_args = DocumentationSearchInput.model_validate(state["action_input"])
            query, sources = input_args.query, input_args.sources
            response = TavilySearchResults(max_results=2).invoke(query)
            state = self.action_output_helper(state, response)
            return state
        except Exception as e:
            return self.handle_tool_error(state, e)

def test_basic_operations():
    splatter = Splatter()
    # Test cases with initial states
    test_cases = [
        # Test file loading
        {
            "messages": [{
                "role": "user",
                "content": "Load and analyze the contents of test_file.py"
            }],
            "current_action_list": [],
            "should_end": False,
            "action_input": {
                "file_path": Path("test_file.py")
            }
        },

        # Test code analysis
        {
            "messages": [{
                "role": "user",
                "content": "Analyze this code: def hello(): print('world')"
            }],
            "current_action_list": [],
            "should_end": False,
            "action_input": {
                "code": "def hello(): print('world')",
                "analysis_type": "general"
            }
        },

        # Test code explanation
        {
            "messages": [{
                "role": "user",
                "content": "Explain this code in detail: for i in range(10): print(i)"
            }],
            "current_action_list": [],
            "should_end": False,
            "action_input": {
                "code": "for i in range(10): print(i)",
                "detail_level": "high"
            }
        }
    ]

    # Run each test case
    for test_case in test_cases:
        result = splatter.graph.invoke(test_case)
        print("\nTest Case Result:")
        print("Messages:", result["messages"])
        print("Action Output:", result.get("action_output"))
        print("Observation:", result.get("observation"))
        print("-" * 50)

if __name__ == "__main__":
    test_basic_operations()
