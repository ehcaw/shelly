from typing import Dict, List, TypedDict, Optional, Any, Set, Tuple
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, SecretStr
from shelly_types.types import CustomRichLog
from shelly_types.utils import find_file
from shelly_types.ollama_embedding import OllamaEmbedding
from cli.terminal_wrapper import TerminalWrapper
from langchain.prompts import ChatPromptTemplate
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_community.tools.tavily_search import TavilySearchResults
from langgraph.prebuilt import create_react_agent
from langchain_groq import ChatGroq
import os
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urlparse, urljoin

#vector store imports
import chromadb
from langchain_chroma import Chroma
from uuid import uuid4
from langchain_core.documents import Document
from langchain_ollama import OllamaEmbeddings
from chromadb.utils import embedding_functions

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
            ("system", "You are a helpful AI coding assistant. Provide clear and concise responses for the user's requests. Use a combination of your own knowledge and the context, with more emphasis on using the context."),
            ("user", "{input}"),
            ("user", "Here are previous messages you should use for context: {context}"),
            ("user", "Here is the context from the knowledge base: {knowledge_base_context}")
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

        # Child terminal wrapper
        self.terminal_wrapper = TerminalWrapper()

        # Knowledge base
        self.knowledge_base = EnhancedKnowledgeBase()


    def process_input(self, state: SimpleState) -> SimpleState:
        try:
            lines = state["current_input"].splitlines()
            processed_input = self.process_commands(lines, state)
            context, context_metadata = self.knowledge_base.vector_store.query(state["current_input"], filter=None)
            self.output_log.write("context " + str(context))
            messages = self.prompt.format_messages(
                input=str(processed_input),
                context=state["messages"],
                knowledge_base_context=str(context) if context else ""
            )

            # Initialize accumulated response
            full_response = ""

            # Stream directly to RichLog
            #stream = self.llm.stream(messages)
            response = self.llm.invoke(messages)

            # Write assistant indicator as a single segment
            self.output_log.write("\nAssistant: ")
            '''
            buffer = ""
            for chunk in stream:
                if chunk.content:
                    # Buffer the content and write in larger chunks
                    buffer += chunk.content
                    if len(buffer) >= 10 or '.' in buffer or '?' in buffer or '!' in buffer:
                        self.output_log.write(buffer, animate=True)
                        full_response += buffer
                        buffer = ""x

            # Write any remaining buffer
            if buffer:
                self.output_log.write(buffer)
                full_response += buffer
            '''
            self.output_log.write(str(response.content))
            # Add final newline
            self.output_log.write("\n")

            # Update state with messages
            state["messages"].append({
                "role": "user",
                "content": state["current_input"]
            })

            state["messages"].append({
                "role": "assistant",
                "content": full_response
            })

            state["current_messages"] = messages
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
            elif line.startswith("/start "):
                self.start_terminal_session()
            elif line.startswith("/link "):
                # add link contents to knowledge base
                processed_lines = self.add_link(line, processed_lines)
            elif line.startswith("/docs "):
                # add doc contents to knowledge base
                processed_lines = self.add_docs(line, processed_lines)
            elif line.startswith("/search "):
                processed_lines = self.search(line, processed_lines)
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
        file_contents_with_linenums = ""
        if relative_file_path:
            with relative_file_path.open() as file:
                for line_num, line in enumerate(file, start=1):
                    file_contents_with_linenums += f'{line_num},{line}\n'
            processed_lines.append(file_contents_with_linenums)
        if len(file_contents_with_linenums) > 0:
            self.knowledge_base.add_entry(str(relative_file_path), file_contents_with_linenums, str(relative_file_path))
        return processed_lines

    def add_directory(self, line, processed_lines):
        dir = line.split('/dir ', 1)[1].strip()
        dir_path = Path(dir)
        all_content = {}
        for file_path in dir_path.rglob('*'):
            relative_file_path = find_file(str(file_path))
            if relative_file_path:
                file_contents_with_linenums = ""
                with relative_file_path.open() as file:
                #all_content[str(file_path)] = relative_file_path.read_text()
                    for line_num, line in enumerate(file, start=1):
                        file_contents_with_linenums += f'{line_num},{line}\n'
                    all_content[str(file_path)] = file_contents_with_linenums
                    self.knowledge_base.add_entry(str(relative_file_path), file_contents_with_linenums, str(relative_file_path))
        processed_lines.append(str(all_content))
        return processed_lines

    def add_link(self, line, processed_lines):
        link = line.split('/link ', 1)[1].strip()
        link_contents = self.knowledge_base.web_scraper.scrape_website(link)
        self.knowledge_base.add_entry(link, link_contents, link)
        return processed_lines

    def add_docs(self, line, processed_lines):
        link = line.split('/link ', 1)[1].strip()
        doc_contents = self.knowledge_base.web_scraper.scrape_documentation(link)
        for link, link_contents in doc_contents.items():
            self.knowledge_base.add_entry(link, link_contents, link)
        return processed_lines

    def search(self, line, processed_lines):
        query = line.split('/search ', 1)[1].strip()
        query_results = self.knowledge_base.web_scraper.search(query)
        self.knowledge_base.add_entry(query, query_results, query)
        processed_lines.append(query + "\n")
        return processed_lines

    def start_terminal_session(self):
        self.terminal_wrapper.open_terminal()

    #def pull_from_terminal(self):



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
    def __init__(self, vector_store):
        self.visited_urls: Set[str] = set()
        self.session = requests.Session()
        self.max_depth = 3
        self.search_engine = TavilySearchResults(max_results=self.max_depth)
        self.vector_store = vector_store

        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        self.llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key= SecretStr(api_key),
            temperature=0,
            stop_sequences=None)

        self.search_agent = create_react_agent(self.llm, [self.search_engine])

    def get_links(self, link: str):
        links_to_scrape = set()
        response = self.session.get(link)
        soup = BeautifulSoup(response.text, 'html.parser')
        base_part = link.split('/')[0] + '//' + link.split('/')[2]
        for link in soup.find_all('a'):
            if self.is_web_link(link) and link.startswith(base_part):
                links_to_scrape.add(link)
        return list(links_to_scrape)

    def clean_text(self, soup: BeautifulSoup):
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text()
        text = re.sub(r"\s+", " ", text).strip()
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

    def scrape_website(self, base_url: str) -> str:
        try:
            response = self.session.get(base_url)
            soup = BeautifulSoup(response.text, 'html.parser')
            cleaned_website_contents = self.clean_text(soup)
            return cleaned_website_contents
        except Exception as e:
            return ""

    def scrape_documentation(self, base_url: str) -> dict:
        content_set = dict() #some websites have diff links but same website
        related_links = [base_url] + self.get_links(base_url)
        for link in related_links:
            try:
                response = self.session.get(link)
                soup = BeautifulSoup(response.text, 'html.parser')
                text = self.clean_text(soup)
                if text not in content_set.values():
                    content_set["link"] = text
            except Exception as e:
                continue
        return content_set

    def search(self, query) -> str:
        response = self.search_engine.invoke({
            "messages": [HumanMessage(content=query)]
        })
        return response['messages'][-1].content

class ChromaStore:
    def __init__(self):
        self.embeddings = OllamaEmbedding(model_name="nomic-embed-text")
        self.persistent_client = chromadb.PersistentClient()
        self.vector_store = Chroma(
            client=self.persistent_client,
            collection_name="shelly",
            embedding_function=self.embeddings
        )
        self.retriever = self.vector_store.as_retriever(
            search_type="mmr", search_kwargs={"k":1, "fetch_k":5}
        )

    # Improvements for single document addition
    def add_document(self, source: str, content: str) -> str:
        doc_id = str(uuid4())  # Convert UUID to string for consistency
        document = Document(
            page_content=content,
            metadata={
                "source": source,
                "timestamp": datetime.now().isoformat(),  # Add timestamp
                "doc_id": doc_id  # Add ID to metadata
            },
            id=doc_id
        )
        try:
            self.vector_store.add_documents(documents=[document], ids=[doc_id])
            return doc_id
        except Exception as e:
            raise

    # Improvements for batch addition
    def add_multiple_documents(
        self,
        sources: List[str],
        contents: List[str],
        batch_size: int = 100
    ) -> List[str]:
        if len(sources) != len(contents):
            raise ValueError("Sources and contents must have same length")

        all_ids = []
        vector_documents = []

        # Process in batches
        for i in range(0, len(sources), batch_size):
            batch_sources = sources[i:i + batch_size]
            batch_contents = contents[i:i + batch_size]

            batch_docs = []
            batch_ids = []

            for source, content in zip(batch_sources, batch_contents):
                doc_id = str(uuid4())
                document = Document(
                    page_content=content,
                    metadata={
                        "source": source,
                        "timestamp": datetime.now().isoformat(),
                        "doc_id": doc_id,
                        "batch_id": i // batch_size
                    },
                    id=doc_id
                )
                batch_docs.append(document)
                batch_ids.append(doc_id)

            try:
                self.vector_store.add_documents(
                    documents=batch_docs,
                    ids=batch_ids
                )
                all_ids.extend(batch_ids)
            except Exception as e:
                raise

        return all_ids

    # Improved query method
    def query(
        self,
        query: str,
        filter: Optional[dict] = None,
        top_k: int = 1,
        fetch_k: int = 5
    ) -> Tuple[List[Document], dict]:
        try:
            # Allow dynamic adjustment of retrieval parameters
            if top_k != self.retriever.search_kwargs["k"] or \
                fetch_k != self.retriever.search_kwargs["fetch_k"]:
                self.retriever.search_kwargs.update({
                    "k": top_k,
                    "fetch_k": fetch_k
                })

            results = self.retriever.invoke(query, filter=filter)

            # Add query metadata
            query_metadata = {
                "timestamp": datetime.now().isoformat(),
                "query": query,
                "filter": filter,
                "top_k": top_k,
                "fetch_k": fetch_k
            }

            return results, query_metadata
        except Exception as e:
            raise

    # Add utility methods
    def get_collection_stats(self) -> dict:
        """Get statistics about the vector store"""
        try:
            collection = self.vector_store.get()
            return {
                "count": len(collection["ids"]),
                "dimension": len(collection["embeddings"][0]) if collection["embeddings"] else 0,
                "metadata": collection["metadatas"]
            }
        except Exception as e:
            raise

    def delete_documents(self, ids: List[str]) -> None:
        """Delete documents by ID"""
        try:
            self.vector_store.delete(ids=ids)
        except Exception as e:
            raise


class EnhancedKnowledgeBase:
    def __init__(self, max_size: int = 100):
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.vector_store = ChromaStore()
        self.web_scraper = WebScraper(self.vector_store)
        #self.project_contexts: Dict[Path, ProjectContext] = {}
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
        self.vector_store.add_document(source, content)
        #logger.info(f"Added entry to knowledge base: {key}")
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
            #logger.info(f"Removed entry from knowledge base: {key}")
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
