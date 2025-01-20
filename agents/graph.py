from typing import Dict, List, TypedDict, Optional, Any, Set
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, SecretStr,
from shelly_types.types import CustomRichLog
from shelly_types.utils import find_file
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin


load_dotenv()

# Define our state structure
class SimpleState(TypedDict):
    messages: List[Dict[str, str]]  # Store conversation history
    current_messages: List[BaseMessage]
    current_input: str              # Current user input
    action_output: str             # Current response
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
            current_messages = [],
            current_input="",
            action_output="",
            should_end=False
        )

        # Create and compile the graph
        self.graph = self.create_graph()

    def process_input(self, state: SimpleState) -> SimpleState:
        try:

            lines = state["current_input"].splitlines()
            processed_input = self.process_commands(lines, state)

            messages = self.prompt.format_messages(
                input=processed_input,
                context=state["messages"]
            )

            # Don't stream here - just set up the stream
            state["messages"].append({
                "role": "user",
                "content": state["current_input"]
            })

            # Store messages for streaming
            state["current_messages"] = messages

            # Mark that we're ready to end
            state["should_end"] = True

            return state
        except Exception as e:
            state["action_output"] = f"Error processing input: {str(e)}"
            state["should_end"] = True
            return state

    def process_commands(self, lines, state):
        processed_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.startswith("/file "):
                processed_lines = self.add_file(line, processed_lines)
            elif line.startswith("/dir "):
                processed_lines = self.add_directory(line, processed_lines)
            else:
                processed_lines.append(line)
        return "\n".join(processed_lines)

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
        self.state = self.graph.invoke(self.state)

        # Return the final output
        return self.state["action_output"]

    def add_file(self, line, processed_lines):
        file_path = line.split('/file ', 1)[1].strip()
        relative_file_path = find_file(file_path)
        if relative_file_path:
            file_contents = relative_file_path.read_text()
            processed_lines.append(file_contents)
        return processed_lines

    def add_directory(self, line, processed_lines):
        dir = line.split('/dir ', 1)[1].strip()
        dir_path = Path(dir)
        all_content = {}
        for file_path in dir_path.rglob('*'):
            relative_file_path = find_file(str(file_path))
            if relative_file_path:
                all_content[str(file_path)] = relative_file_path.read_text()
        processed_lines.append(str(all_content))
        return processed_lines


class KnowledgeEntry:
    def __init__(self, content: Any, source: str, timestamp: datetime):
        self.content = content
        self.source = source
        self.timestamp = timestamp
        self.access_count = 0
        self.last_accessed = timestamp

    def access(self):
        self.access_count += 1
        self.last_accessed = datetime.now()

class WebScraper:
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.session = requests.Session()
        self.max_depth = 3

    def get_links(self, soup: BeautifulSoup):
        links_to_scrape = set()
        for link in soup.find_all('a'):
            if self.is_web_link(link):
                links_to_scrape.add(link)
        return list(links_to_scrape)

    def clean_text(self, soup: BeautifulSoup)
        text = soup.get_text(separator=' ')

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Strip leading/trailing space
        text = text.strip()

        return text

    def is_web_link(self, href: str, base_url: str = None) -> bool:
        """
        Determine if an href is a web link.

        Args:
            href: The href value to check
            base_url: Optional base URL for resolving relative URLs

        Returns:
            bool: True if it's a web link, False otherwise
        """
        if not href:
            return False

        # Ignore common non-web patterns
        if href.startswith(('#', 'javascript:', 'mailto:', 'tel:', 'sms:', 'file:')):
            return False

        # Handle relative URLs if base_url is provided
        if base_url:
            href = urljoin(base_url, href)

        try:
            parsed = urlparse(href)
            return bool(parsed.netloc) and parsed.scheme in ('http', 'https')
        except:
            return False
    #def scrape_documentation(self, base_url: str):



class EnhancedKnowledgeBase:
    def __init__(self, max_size: int = 1000):
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.web_scraper = WebScraper()
        self.project_contexts: Dict[Path, ProjectContext] = {}
        self.max_size = max_size
    def add_entry(self, key: str, content: Any, source: str):
        """Add an entry to the knowledge base"""
        if len(self.entries) >= self.max_size:
            self._cleanup()
        self.entries[key] = KnowledgeEntry(
            content=content,
            source=source,
            timestamp=datetime.now(),
        )
        logger.info(f"Added entry to knowledge base: {key}")
    def get_entry(self, key: str) -> Optional[Any]:
        """Get an entry from the knowledge base"""
        entry = self.entries.get(key)
        if entry:
            entry.access()
            return entry.content
        return None

    def _cleanup(self):
        """Clean up least used entries"""
        sorted_entries = sorted(
            self.entries.items(),
            key=lambda x: (x[1].access_count, x[1].last_accessed)
        )
        entries_to_remove = int(len(self.entries) * 0.2)
        for key, _ in sorted_entries[:entries_to_remove]:
            del self.entries[key]
            logger.info(f"Removed entry from knowledge base: {key}")
def main():
    chat = SimpleChat()
    print("Chat started. Type 'exit', 'quit', or 'bye' to end the conversation.")

    while True:
        user_input = input("You: ")
        if user_input.lower().strip() in ["exit", "quit", "bye"]:
            break
        response = chat.chat(user_input)
        print(f"Assistant: {response}")

#main()
