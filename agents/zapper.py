from collections import defaultdict
from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_ollama import ChatOllama
from typing import Annotated, List, Optional
from langgraph.graph.state import CompiledStateGraph
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import tool
from langgraph.types import interrupt
from dotenv import load_dotenv
import os
import subprocess
import tomllib
from pydantic import SecretStr, BaseModel, Field
from utils.utils import calculate_semantic_similarity


load_dotenv()


class GraphState(TypedDict):
    messages: Annotated[list, add_messages]
    next: Optional[str]
    counter: int


class ErrorExplanation(BaseModel):
    error_type: str = Field(description="The type of error encountered")
    explanation: str = Field(description="Detailed explanation of the error")
    suggested_fixes: List[str] = Field(description="List of potential fixes for the error")


def explainer_llm_selection():
    #with open("config.toml", "rb") as f:
        #config = tomllib.load(f)
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    return ChatGroq(
            model="llama-3.1-8b-instant",
            api_key= SecretStr(api_key),
            temperature=0,
            stop_sequences=None,
    )
def corrector_llm_selection():
    api_key = os.getenv('GROQ_API_KEY')
    if not api_key:
        raise ValueError("GROQ_API_KEY environment variable is not set")
    return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key= SecretStr(api_key),
            temperature=0,
            stop_sequences=None)

class Zapper:
    llm: ChatGroq | ChatOpenAI | ChatAnthropic | ChatOllama
    state: GraphState
    graph_builder: StateGraph
    graph: CompiledStateGraph
    def __init__(self):
        self.explainer_llm = explainer_llm_selection()
        self.corrector_llm = corrector_llm_selection()
        self.graph_builder = StateGraph(GraphState)
        self.parser = PydanticOutputParser(pydantic_object=ErrorExplanation)
        self.init_graph(self.graph_builder)


    def prompt(self, state: GraphState):
        return { "messages": [self.llm.invoke(state["messages"])]}

    def explain_error(self, state: GraphState):
        prompt = ChatPromptTemplate.from_messages([("system", """You are an expert programming assistant.
                    Analyze the error and provide a structured response.
                    If you are unable to provide a good structured response, do not return anything at all.
                    {format_instructions}"""),
                    ("user", "{traceback}"),
                    ("user", "{error_information}")])
        traceback, error_information = state["messages"][-1]["traceback"], state["messages"][-1]["error_information"]
        formatted_prompt = prompt.format_messages(
            format_instructions=self.parser.get_format_instructions(),
            traceback=traceback,
            error_information=error_information
        )
        if traceback and error_information:
            response = self.llm.invoke(formatted_prompt)

            parsed_response = self.parser.parse(str(response.content))
        else:
            parsed_response = None
        return {"messages": state["messages"] + [{
            "role": "assistant",
            "content": parsed_response.model_dump() if parsed_response else ""
        }]}

    def run_branch(self, state: GraphState) -> dict:
        command = state["messages"][-1]
        try:
            subprocess.run(command, capture_output=True, check=True, text=True)
        except subprocess.CalledProcessError as error:
            traceback: str = error.stderr if error.stderr else str(error)
            error_information = str(error)
            return {
                "messages": state["messages"] + [
                    {
                        "traceback": traceback,
                        "error_information": error_information
                    } # the error traceback and error information are added to the graph messages
                ],
                "next": "analyze_branch",
                "counter": state["counter"] + 1
            }
        return {
            "messages": state["messages"] + [
                {"traceback": None,
                "error_information": None
                }# the error traceback and error information are added to the graph messages
            ],
            "next": "analyze_branch",
            "counter": state["counter"] + 1
        }

    def analyze_branch(self, state: GraphState):
        error_object = state["messages"][-1]


    def evaluate_input(self, state: GraphState) -> dict:
        last_message = state["messages"][-1]

        # Extract content based on message type
        if isinstance(last_message, tuple):
            message_content = last_message[1]
        elif hasattr(last_message, 'content'):
            message_content = last_message.content
        else:
            message_content = str(last_message)

        # Return state dict and include next step in metadata
        if calculate_semantic_similarity("help", message_content) > 0.5:
            return {
                "messages": state["messages"] + [
                    AIMessage(content="Routing to help...")
                ],
                "next": "help_branch",
                "counter": state["counter"] + 1
            }
        elif calculate_semantic_similarity("fix", message_content) > 0.5 or \
                calculate_semantic_similarity("debug", message_content) > 0.5:
            return {
                "messages": state["messages"] + [
                    AIMessage(content="Routing to fix...")
                ],
                "next": "fix_branch",
                "counter": state["counter"] + 1
            }
        else:
            return {
                "messages": state["messages"] + [
                    AIMessage(content="Completing interaction...")
                ],
                "next": "done_branch",
                "counter": state["counter"] + 1
            }

    def help_branch(self, state: GraphState) -> dict:
        # Print the help message
        help_message = ("I'm here to help! What would you like to know?\n"
                        "- Type 'fix' to get help fixing an issue\n"
                        "- Type 'help' for general assistance\n"
                        "- Type 'done' to finish")
        return {
            "messages": state["messages"] + [
                AIMessage(content=help_message)
            ],
            "next": "wait_for_input",  # Transition to wait state
            "counter": state["counter"] + 1
        }

    def fix_branch(self, state: GraphState) -> dict:

        fix_message = ("Let's fix that issue!\n"
                        "- Describe your problem in detail\n"
                        "- Type 'help' if you need different assistance\n"
                        "- Type 'done' when the issue is resolved")
        return {
            "messages": state["messages"] + [
                AIMessage(content=fix_message)
            ],
            "next": "wait_for_input",  # Transition to wait state
            "counter": state["counter"] + 1
        }

    def done_branch(self, state: GraphState) -> dict:
        return {
            "messages": state["messages"] + [
                AIMessage(content="Thanks for using the assistance! Goodbye!")
            ],
            "next": END, # end of conversation
            "counter": state["counter"] + 1
        }

    def wait_for_input(self, state: GraphState) -> dict:
            """Wait for user input before continuing"""

            # Get user input
            user_input = input("You: ")

            # Add user input to state
            return {
                "messages": state["messages"] + [
                    HumanMessage(content=user_input)
                ],
                "next": self.determine_next_step(user_input),
                "counter": state["counter"] + 1
            }
    def determine_next_step(self, user_input: str) -> str:
            """Determine next step based on user input"""
            if calculate_semantic_similarity("done", user_input) > 0.5:
                return "done_branch"
            elif calculate_semantic_similarity("help", user_input) > 0.5:
                return "help_branch"
            elif calculate_semantic_similarity("fix", user_input) > 0.5:
                return "fix_branch"
            else:
                return "help_branch"

    def cyclic_router(self, state: GraphState):
        """
        Routes between help, fix, and done states based on the last message
        """
        try:
            # Get the last message from the state
            message = state["messages"][-1][1]  # Assuming message is a tuple of (role, content)
            print(f"Cyclic router processing: {message}")

            # Check message content and route accordingly
            if calculate_semantic_similarity("done", message) > 0.5:
                print("Routing to done_branch")
                return "done_branch"
            elif calculate_semantic_similarity("help", message) > 0.5:
                print("Routing to help_branch")
                return "help_branch"
            elif calculate_semantic_similarity("fix", message) > 0.5 or \
                 calculate_semantic_similarity("debug", message) > 0.5:
                print("Routing to fix_branch")
                return "fix_branch"
            else:
                # Default to help branch if we can't determine the intent
                print("Default routing to help_branch")
                return "help_branch"
        except Exception as e:
            print(f"Error in cyclic_router: {e}")
            return "help_branch"  # Default fallback


    def init_graph(self, graph_builder: StateGraph):
        # Add nodes
        graph_builder.add_node("entry_point", self.evaluate_input)
        graph_builder.add_node("help_branch", self.help_branch)
        graph_builder.add_node("fix_branch", self.fix_branch)
        graph_builder.add_node("wait_for_input", self.wait_for_input)
        graph_builder.add_node("done_branch", self.done_branch)

        # Define edges
        graph_builder.add_conditional_edges(
            "entry_point",
            lambda x: x["next"],
            {
                "help_branch": "help_branch",
                "fix_branch": "fix_branch",
                "done_branch": "done_branch",
                "wait_for_input": "wait_for_input"
            }
        )

        # Add edges from wait_for_input
        graph_builder.add_conditional_edges(
            "wait_for_input",
            lambda x: x["next"],
            {
                "help_branch": "help_branch",
                "fix_branch": "fix_branch",
                "done_branch": "done_branch"
            }
        )

        # Add edges from help and fix branches
        for branch in ["help_branch", "fix_branch"]:
            graph_builder.add_conditional_edges(
                branch,
                lambda x: x["next"],
                {
                    "wait_for_input": "wait_for_input",
                    "done_branch": "done_branch"
                }
            )

        # Terminal edge
        graph_builder.add_edge("done_branch", END)

        # Set entry point
        graph_builder.set_entry_point("entry_point")

        # Compile graph
        self.graph = graph_builder.compile()

    def stream_graph_updates(self, user_input: str):
        for event in self.graph.stream({
            "messages": [("user", user_input)]
        }):
            for key, value in event.items():
                if "messages" in value and value["messages"]:
                    message = value["messages"][-1]
                    if isinstance(message, tuple):
                        print(f"Assistant: {message[1]}")
                    else:
                        print(f"Assistant: {message}")
    def return_graph_updates(self, error_input: str):
        responses = []
        for event in self.graph.stream({"messages": [("user", error_input)]}):
            llm_response = defaultdict()
            for value in event.values():
                response = value["messages"][-1]["content"]
                llm_response["error_type"] = response["error_type"]
                llm_response["explanation"] = response["explanation"]
                llm_response["suggested_fixes"] = response["suggested_fixes"]
                llm_response["code_example"] = response["code_example"]
            print(llm_response["code_example"])
            responses.append(llm_response)
        return responses

    #tool
    def apply_fixes(self, code_fixes: List[str], files: List[str]):
        code_fixes_and_files = zip(code_fixes, files)
        for fix in code_fixes_and_files:
            # apply fix
            print(fix)

def main():
    zapper = Zapper()
    #zapper.stream_graph_updates("tell me about langchain")


if __name__ == "__main__":
    main()
