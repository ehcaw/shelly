from langchain_groq import ChatGroq
from langchain.prompts import ChatPromptTemplate
from langgraph.graph import END, StateGraph, START
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import create_react_agent
from openai import OpenAI

from typing import TypedDict, List, Dict, Optional
from pydantic import SecretStr, BaseModel, Field
import os
import difflib


class CodeFile(TypedDict):
    name: str
    path: str
    content: str

class ContextState(TypedDict):
    messages: List[BaseMessage]
    code_files: List[CodeFile]

class GraphState(TypedDict):
    """
    Represents the state of our graph.

    Attributes:
        error : Binary flag for control flow to indicate whether test error was tripped
        messages : With user question, error messages, reasoning
        generation : Code solution
        iterations : Number of tries
    """

    error: str
    messages: List
    generation: str
    iterations: int

class LLMGeneration(BaseModel):
    """Schema for code solutions."""
    file_path: str = Field(description="The path of the file if the code is for a file provided in the context. Otherwise, put '""'")
    prefix: str = Field(description="Description of the problem and approach")
    imports: str = Field(description="Any new import statements needed")
    edit_type: str = Field(description="Type of edit: 'full_replacement', 'targeted_edit', or 'new_file'")
    start_line: int = Field(description="Starting line number for targeted edits (use 0 for full replacements or new files)")
    end_line: int = Field(description="Ending line number for targeted edits (use 0 for full replacements or new files)")
    original_code: str = Field(description="The original code being replaced (for targeted edits only, otherwise empty string)")
    code: str = Field(description="The new code to insert or replace with")

code_gen_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """<instructions> You are a coding assistant with expertise in writing code without error. You desperately
                        need money for your mother's cancer treatment. You have been given an opportunity to write code in exchange
                        for a billion dollars so that you can pay for her treatment, provided that you write well formatted code and accomplish the user's request fully.
                        Otherwise, you will be terminated brutally.
                        Here is the context for you to reference to write any code that the user requests \n ------- \n  {context} \n ------- \n

                        When making code changes:

                        1. If you're modifying an existing file, use targeted edits whenever possible:
                           - Identify the specific lines that need to change
                           - Set edit_type to 'targeted_edit'
                           - Provide the start_line and end_line numbers
                           - Include the original_code being replaced
                           - Provide the new code that should replace it

                        2. If you need to replace an entire file or create a new one:
                           - Set edit_type appropriately ('full_replacement' or 'new_file')
                           - Set start_line and end_line to 0
                           - Provide the complete new code

                        Structure your answer with: 1) a prefix describing the solution, 2) any new imports needed,
                        3) details about what code to modify and how.

                        Always format code blocks with triple backticks and the appropriate language identifier:
                        ```python
                        # Your Python code here
                        ```

                        For file contents in your response, also use triple backticks with language identifiers.

                        Ensure your code is properly indented and follows best practices for readability.

                        Invoke the code tool to structure the output correctly.
                        </instructions> \n Here is the user question:""",
        ),
        ("placeholder", "{messages}"),
    ]
)

class ArchitectModel:
    max_iterations = 3
    flag = "do not reflect"
    def __init__(self, code_files: Optional[List[CodeFile]]):
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        self.llm = ChatGroq(
                model="llama-3.3-70b-versatile",
                api_key= SecretStr(api_key),
                temperature=0,
                stop_sequences=None).with_structured_output(LLMGeneration, include_raw = True)
        self.deepseek = ChatGroq(
            model="deepseek-r1-distill-qwen-32b",
            api_key=SecretStr(api_key),
            temperature=0,
            stop_sequences=None)

        #self.deepseek = OpenAI(api_key=os.getenv('DEEPSEEK_API_KEY'), base_url="https://api.deepseek.com")
        self.architect_state = ContextState(messages=[], code_files=code_files if code_files else [])

        self.code_chain_raw = (
             code_gen_prompt | self.llm | self.check_output
        )
        self.code_gen_chain = (
            code_gen_prompt | self.llm
        )
        self.fallback_chain = self.insert_errors | self.code_chain_raw
        N = 3  # Max re-tries
        self.code_gen_chain_re_try = self.code_chain_raw.with_fallbacks(
            fallbacks=[self.fallback_chain] * N, exception_key="error"
        )
        self.graph = self.construct_graph()


    #-------------------TOOLS -----------------------------------#
    def check_output(self, tool_output):
        """Check for parse error or failure to call the tool"""
        # Error with parsing
        if tool_output["parsing_error"]:
            # Report back output and parsing errors
            print("Parsing error!")
            raw_output = str(tool_output["raw"].content)
            error = tool_output["parsing_error"]
            raise ValueError(
                f"Error parsing your output! Be sure to invoke the tool. Output: {raw_output}. \n Parse error: {error}"
            )

        # Tool was not invoked
        elif not tool_output["parsed"]:
            print("Failed to invoke tool!")
            raise ValueError(
                "You did not use the provided tool! Be sure to invoke the tool to structure the output."
            )
        return tool_output

    #------------------------------------------------------#

    def insert_errors(self,inputs):
        """Insert errors for tool parsing in the messages"""

        # Get errors
        error = inputs["error"]
        messages = inputs["messages"]
        messages += [
            (
                "assistant",
                f"Retry. You are required to fix the parsing errors: {error} \n\n You must invoke the provided tool.",
            )
        ]
        return {
            "messages": messages,
            "context": inputs["context"],
        }




    def parse_output(self, solution):
        """When we add 'include_raw=True' to structured output,
        it will return a dict w 'raw', 'parsed', 'parsing_error'."""

        return solution["parsed"]

    def generate(self, state: GraphState):
        """
        Generate a code solution

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, generation
        """

        print("---GENERATING CODE SOLUTION---")

        # State
        messages = state["messages"]
        iterations = state["iterations"]
        error = state["error"]

        # We have been routed back to generation with an error
        if error == "yes":
            messages += [
                (
                    "user",
                    "Now, try again. Invoke the code tool to structure the output with a prefix, imports, and code block:",
                )
            ]


        # Solution
        code_solution = self.code_gen_chain.invoke(
            {"context": self.architect_state["code_files"], "messages": messages}
        )
        print(code_solution)
        code_solution = code_solution["parsed"]
        messages += [
            (
                "assistant",
                f"{code_solution.prefix} \n Imports: {code_solution.imports} \n Code: {code_solution.code}",
            )
        ]

        # Increment
        iterations = iterations + 1
        return {"generation": code_solution, "messages": messages, "iterations": iterations}


    def code_check(self, state: GraphState):
        """
        Check code

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, error
        """

        print("---CHECKING CODE---")

        # State
        messages = state["messages"]
        code_solution = state["generation"]
        iterations = state["iterations"]

        # Get solution components
        imports = code_solution.imports
        code = code_solution.code

        # Check imports
        try:
            exec(imports)
        except Exception as e:
            print("---CODE IMPORT CHECK: FAILED---")
            error_message = [("user", f"Your solution failed the import test: {e}")]
            messages += error_message
            return {
                "generation": code_solution,
                "messages": messages,
                "iterations": iterations,
                "error": "yes",
            }

        # Check execution
        try:
            exec(imports + "\n" + code)
        except Exception as e:
            print("---CODE BLOCK CHECK: FAILED---")
            error_message = [("user", f"Your solution failed the code execution test: {e}")]
            messages += error_message
            return {
                "generation": code_solution,
                "messages": messages,
                "iterations": iterations,
                "error": "yes",
            }

        # No errors
        print("---NO CODE TEST FAILURES---")
        return {
            "generation": code_solution,
            "messages": messages,
            "iterations": iterations,
            "error": "no",
        }


    def reflect(self, state: GraphState):
        """
        Reflect on errors

        Args:
            state (dict): The current graph state

        Returns:
            state (dict): New key added to state, generation
        """

        print("---GENERATING CODE SOLUTION---")

        # State
        messages = state["messages"]
        iterations = state["iterations"]
        code_solution = state["generation"]

        context = self.format_code_files_for_llm()

        # Prompt reflection

        # Add reflection
        #
        #
        reflections = self.code_gen_chain.invoke(
            {"context": context, "messages": messages}
        )
        messages += [("assistant", f"Here are reflections on the error: {reflections}")]
        return {"generation": code_solution, "messages": messages, "iterations": iterations}


    ### Edges


    def decide_to_finish(self, state: GraphState):
        """
        Determines whether to finish.

        Args:
            state (dict): The current graph state

        Returns:
            str: Next node to call
        """
        error = state["error"]
        iterations = state["iterations"]

        if error == "no" or iterations == self.max_iterations:
            print("---DECISION: FINISH---")
            return "end"
        else:
            print("---DECISION: RE-TRY SOLUTION---")
            if self.flag == "reflect":
                return "reflect"
            else:
                return "generate"

    def construct_graph(self):
        workflow = StateGraph(GraphState)
        workflow.add_node("generate", self.generate)  # generation solution
        workflow.add_node("check_code", self.code_check)  # check code
        workflow.add_node("reflect", self.reflect)  # reflect

        # Build graph
        workflow.add_edge(START, "generate")
        workflow.add_edge("generate", "check_code")
        workflow.add_conditional_edges(
            "check_code",
            self.decide_to_finish,
            {
                "end": END,
                "reflect": "reflect",
                "generate": "generate",
            },
        )
        workflow.add_edge("reflect", "generate")
        app = workflow.compile()
        return app

    def find_code_file_by_path(self, path: str):
        for element in self.architect_state["code_files"]:
            if element["path"]== path:
                return element["content"]
        return None

    def format_code_files_for_llm(self):
        resulting_code_files = ""
        for file in self.architect_state["code_files"]:
            resulting_code_files += (
                "=" * 15 + "\n"
                + "Name: " + file["name"] + "\n"
                + "Path: " + file["path"] + "\n"
                + "=" * 15 + "\n"
            )

            lines = file["content"].splitlines()
            for i, line in enumerate(lines):
                resulting_code_files += f"{i:4d} | {line}\n"
            resulting_code_files += "\n\n"
        return resulting_code_files
