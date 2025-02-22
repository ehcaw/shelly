from typing import Dict, List, TypedDict, Optional
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, SecretStr
from shelly_types.types import CustomRichLog
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

# Define our state structure
class SimpleState(TypedDict):
    messages: List[Dict[str, str]]  # Store conversation history
    current_input: str              # Current user input
    current_output: str             # Current response
    should_end: bool               # Flag to end conversation

class SimpleChat:
    """A simple LangGraph implementation that processes user input and returns output."""
    output_log: CustomRichLog
    def __init__(self):
        # Initialize LLM
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")

        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key= SecretStr(api_key),
            temperature=0,
            stop_sequences=None)

        # Create prompt template
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful AI coding assistant. Provide clear and concise responses for the user's requests."),
            ("human", "{input}"),
            ("human", "Here are previous messages you should use for context: {context}")
        ])
        self.state = SimpleState(
            messages=[],
            current_input="",
            current_output="",
            should_end=False
        )

        # Create and compile the graph
        self.graph = self.create_graph()

    def process_input(self, state: SimpleState) -> SimpleState:
        """Process the user input and generate a response."""
        try:
            # Format the prompt with user input
            # load files/directories into the message context
            lines = state["current_input"]
            lines = lines.splitlines()
            for idx, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                if line.startswith("/file "):
                    file_path = line.split('/file ', 1)[1].strip()
                    file_contents = Path(file_path).read_text()
                    line = file_contents
                elif line.startswith("/dir ") or line.startswith("/directory "):
                    all_content = {}
                    dir = line.split('/dir ', 1)[1].strip() if line.startswith('/dir ') else line.split('/directory ', 1)[1].strip()
                    dir_path = Path(dir)
                    for file_path in dir_path.rglob('*'):  # rglob gets all files recursively
                        if file_path.is_file():  # Check if it's a file
                            all_content[str(file_path)] = file_path.read_text()
                    line = str(all_content)

            messages = self.prompt.format_messages(input=lines, context=state["messages"])

            # Get response from LLM
            response = self.llm.invoke(messages)

            # Update state with response
            state["current_output"] = str(response.content)

            # Add to message history
            state["messages"].append({
                "role": "user",
                "content": state["current_input"]
            })
            state["messages"].append({
                "role": "assistant",
                "content": state["current_output"]
            })
            return state

        except Exception as e:
            state["current_output"] = f"Error processing input: {str(e)}"

        return state

    def should_continue(self, state: SimpleState) -> bool:
        """Determine if the conversation should continue."""
        # End if user types 'exit' or 'quit'
        return not (
            state["current_input"].lower().strip() in ["exit", "quit", "bye"]
            or state["should_end"]
        )

    def create_graph(self):
        """Create the workflow graph."""
        # Initialize the graph with our state type
        workflow = StateGraph(SimpleState)

        # Add the main processing node
        workflow.add_node("process", self.process_input)

        # Add edges
        workflow.set_entry_point("process")

        # Add conditional edge back to process or to end
        workflow.add_conditional_edges(
            "process",
            self.should_continue,
            {
                True: "process",    # Continue processing
                False: END          # End the conversation
            }
        )

        return workflow.compile()

    def chat(self, user_input: str) -> str:
        """Main method to interact with the chat."""
        # Initialize state
        self.state["current_input"] = user_input

        # Run the workflow
        final_state = self.graph.invoke(self.state)

        # Return the final output
        return final_state["current_output"]

def main():
    chat = SimpleChat()
    print("Chat started. Type 'exit', 'quit', or 'bye' to end the conversation.")

    while True:
        user_input = input("You: ")
        if user_input.lower().strip() in ["exit", "quit", "bye"]:
            break
        response = chat.chat(user_input)
        print(f"Assistant: {response}")

main()
