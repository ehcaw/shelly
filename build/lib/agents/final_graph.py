from typing import TypedDict, List, Dict, Any, Optional, Set
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
import ast
import asyncio
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel
from langgraph.graph import StateGraph, END, START
from urllib.parse import urlparse, urljoin
from shelly_types.types import CustomRichLog
import importlib.util
import sys
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PipelineType(Enum):
    CODE = "code"
    FILE = "file"
    CONVERSATION = "conversation"
    DOCUMENTATION = "documentation"


class MessageType(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


@dataclass
class Message:
    content: str
    type: MessageType
    timestamp: datetime
    metadata: Dict[str, Any] = None


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


class WebContent:
    def __init__(self, url: str, content: str, metadata: Dict[str, Any]):
        self.url = url
        self.content = content
        self.metadata = metadata
        self.timestamp = datetime.now()
        self.related_urls: Set[str] = set()


class FileNode:
    def __init__(self, path: str, content: str):
        self.path = Path(path)
        self.content = content
        self.imports: List[str] = []
        self.dependencies: Set[Path] = set()
        self.last_modified = datetime.now()
        self.ast_tree = None
        self.symbols: Dict[str, Any] = {}


class ProjectContext:
    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.files: Dict[Path, FileNode] = {}
        self.import_graph: Dict[Path, Set[Path]] = {}
        self.virtual_env_path: Optional[Path] = None
        self.package_dependencies: Dict[str, str] = {}

    async def process_project(self):
        """Process all files in the project"""
        for file_path in self.root_dir.rglob("*.py"):
            if file_path not in self.files:
                await self.process_file(file_path)

    async def process_file(self, file_path: Path):
        """Process a single file"""
        try:
            content = file_path.read_text()
        except Exception as e:
            logger.error(f"Failed to read {file_path}: {e}")
            return

        file_node = FileNode(str(file_path), content)
        self.files[file_path] = file_node
        await self.analyze_file_dependencies(file_node)

    async def analyze_file_dependencies(self, file_node: FileNode):
        """Analyze file dependencies"""
        try:
            tree = ast.parse(file_node.content)
            file_node.ast_tree = tree

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        file_node.imports.append(name.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        file_node.imports.append(node.module)

            await self.resolve_dependencies(file_node)

        except SyntaxError as e:
            logger.warning(f"Syntax error in {file_node.path}: {e}")

    async def resolve_dependencies(self, file_node: FileNode):
        """Resolve file dependencies"""
        for import_name in file_node.imports:
            possible_paths = [
                self.root_dir / f"{import_name.replace('.', '/')}.py",
                self.root_dir / import_name / "__init__.py"
            ]

            for path in possible_paths:
                if path.exists():
                    file_node.dependencies.add(path)
                    if path not in self.import_graph:
                        self.import_graph[path] = set()
                    self.import_graph[path].add(file_node.path)
                    break
            else:
                spec = importlib.util.find_spec(import_name.split('.')[0])
                if spec:
                    self.package_dependencies[import_name.split('.')[0]] = spec.origin or "unknown"


class WebScraper:
    def __init__(self):
        self.visited_urls: Set[str] = set()
        self.session = requests.Session()
        self.max_depth = 3

    async def scrape_documentation(self, base_url: str, allowed_domains: Optional[List[str]] = None) -> Dict[str, WebContent]:
        content_map = {}
        base_domain = urlparse(base_url).netloc
        allowed_domains = allowed_domains or [base_domain]

        await self._scrape_url(base_url, content_map, allowed_domains, depth=0)
        return content_map

    async def _scrape_url(self, url: str, content_map: Dict[str, WebContent], allowed_domains: List[str], depth: int):
        if depth >= self.max_depth or url in self.visited_urls:
            return

        if not any(domain in urlparse(url).netloc for domain in allowed_domains):
            return

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            content = self._extract_main_content(soup)
            metadata = self._extract_metadata(soup)

            web_content = WebContent(url, content, metadata)
            content_map[url] = web_content
            self.visited_urls.add(url)

            tasks = []
            for link in soup.find_all('a', href=True):
                next_url = urljoin(url, link['href'])
                if next_url not in self.visited_urls:
                    web_content.related_urls.add(next_url)
                    tasks.append(self._scrape_url(next_url, content_map, allowed_domains, depth + 1))

            await asyncio.gather(*tasks)

        except requests.RequestException as e:
            logger.error(f"Error scraping {url}: {e}")

    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
        if main_content:
            return main_content.get_text(separator='\n', strip=True)
        return soup.get_text(separator='\n', strip=True)

    def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
        meta_description = soup.find('meta', {'name': 'description'})
        meta_description_content = meta_description['content'] if meta_description else None

        return {
            'title': soup.title.string if soup.title else None,
            'meta_description': meta_description_content,
            'h1': [h1.get_text(strip=True) for h1 in soup.find_all('h1')],
        }


class KnowledgeEntry(BaseModel):
    content: Any
    source: str
    timestamp: datetime
    access_count: int = 0
    last_accessed: datetime

    class Config:
        arbitrary_types_allowed = True

    def access(self):
        self.access_count += 1
        self.last_accessed = datetime.now()


class EnhancedKnowledgeBase:
    def __init__(self, max_size: int = 1000):
        self.entries: Dict[str, KnowledgeEntry] = {}
        self.web_scraper = WebScraper()
        self.project_contexts: Dict[Path, ProjectContext] = {}
        self.max_size = max_size

    async def add_entry(self, key: str, content: Any, source: str):
        """Add an entry to the knowledge base"""
        if len(self.entries) >= self.max_size:
            self._cleanup()
        self.entries[key] = KnowledgeEntry(
            content=content,
            source=source,
            timestamp=datetime.now(),
            last_accessed=datetime.now()
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

    async def load_documentation(self, url: str, allowed_domains: Optional[List[str]] = None):
        """Load documentation from a URL"""
        content_map = await self.web_scraper.scrape_documentation(url, allowed_domains)

        for url, web_content in content_map.items():
            await self.add_entry(
                f"doc:{url}",
                {
                    "content": web_content.content,
                    "metadata": web_content.metadata,
                },
                source="web_documentation"
            )
        logger.info(f"Loaded documentation from {url}")

    async def load_project(self, root_dir: str):
        """Load a project into the knowledge base"""
        root_path = Path(root_dir)
        if root_path not in self.project_contexts:
            self.project_contexts[root_path] = ProjectContext(root_path)

        project_context = self.project_contexts[root_path]
        await project_context.process_project()

        # Add project structure to knowledge base
        project_structure = {
            "files": [str(path) for path in project_context.files.keys()],
            "dependencies": project_context.package_dependencies,
            "import_graph": {
                str(k): [str(v) for v in vs]
                for k, vs in project_context.import_graph.items()
            }
        }
        await self.add_entry(
            f"project:{root_dir}",
            project_structure,
            source="project_context"
        )
        logger.info(f"Loaded project from {root_dir}")


class WorkflowState(BaseModel):
    messages: List[Message] = []
    knowledge_base: EnhancedKnowledgeBase
    pipeline_type: Optional[PipelineType] = None
    current_step: Dict[str, Any] = {}
    operation_stack: List[str] = []
    temporary_storage: Dict[str, Any] = {}
    should_end: bool = False

    class Config:
        arbitrary_types_allowed = True


class Splatter:
    def __init__(self):
        # Initialize core components
        self.state: Optional[WorkflowState] = None
        self.workflow: Optional[StateGraph] = None
        self.knowledge_base = EnhancedKnowledgeBase()
        self.initialize_components()

    def initialize_components(self):
        """Initialize all core components"""
        self.state = WorkflowState(knowledge_base=self.knowledge_base)
        self.workflow = self.create_workflow_graph()

    # ============= Pipeline Handlers =============
    async def handle_documentation(self, state: WorkflowState) -> WorkflowState:
        """Handle documentation loading requests"""
        try:
            state.operation_stack.append("documentation_loading")
            url = state.messages[-1].content
            await state.knowledge_base.load_documentation(url)

            state.messages.append(Message(
                content=f"Documentation from {url} has been loaded.",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
            logger.info(f"Handled documentation for {url}")
        except Exception as e:
            logger.error(f"Error handling documentation: {e}")
            state.messages.append(Message(
                content=f"Failed to load documentation from {url}: {e}",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
        finally:
            state.operation_stack.pop()

        return state

    async def handle_files(self, state: WorkflowState) -> WorkflowState:
        """Handle file operations"""
        try:
            state.operation_stack.append("file_operation")
            path = state.current_step.get("path")
            if not path:
                raise ValueError("No path provided for file operation.")

            await state.knowledge_base.load_project(path)

            state.messages.append(Message(
                content=f"Loaded project from {path}.",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
            logger.info(f"Handled file operation for {path}")
        except Exception as e:
            logger.error(f"Error handling files: {e}")
            state.messages.append(Message(
                content=f"Failed to load project from {path}: {e}",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
        finally:
            state.operation_stack.pop()

        return state

    async def handle_code(self, state: WorkflowState) -> WorkflowState:
        """Handle code operations"""
        try:
            state.operation_stack.append("code_operation")
            # Placeholder for code handling logic
            # Implement actual code handling here
            state.messages.append(Message(
                content="Code operation completed.",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
            logger.info("Handled code operation.")
        except Exception as e:
            logger.error(f"Error handling code: {e}")
            state.messages.append(Message(
                content=f"Code operation failed: {e}",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
        finally:
            state.operation_stack.pop()

        return state

    async def handle_conversation(self, state: WorkflowState) -> WorkflowState:
        """Handle conversation"""
        try:
            state.operation_stack.append("conversation")
            # Placeholder for conversation handling logic
            # Implement actual conversation handling here
            user_message = state.messages[-1].content
            assistant_response = f"Echo: {user_message}"
            state.messages.append(Message(
                content=assistant_response,
                type=MessageType.ASSISTANT,
                timestamp=datetime.now()
            ))
            logger.info("Handled conversation.")
        except Exception as e:
            logger.error(f"Error handling conversation: {e}")
            state.messages.append(Message(
                content=f"Conversation handling failed: {e}",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
        finally:
            state.operation_stack.pop()

        return state

    # ============= Graph Creation =============
    def create_workflow_graph(self):
        """Create the workflow graph with proper start and end conditions"""
        workflow = StateGraph(WorkflowState)

        # Add entry point node
        workflow.add_node("initialize_session", self.initialize_session)

        # Add main nodes
        workflow.add_node("router", self.route_request)
        workflow.add_node("documentation_handler", self.handle_documentation)
        workflow.add_node("file_handler", self.handle_files)
        workflow.add_node("code_handler", self.handle_code)
        workflow.add_node("conversation_handler", self.handle_conversation)

        # Add cleanup/end node
        workflow.add_node("cleanup", self.cleanup_session)

        # Start -> Initialize Session -> Router edge
        workflow.add_edge(START, "initialize_session")
        workflow.add_edge("initialize_session", "router")

        # Router -> Handler edges
        workflow.add_conditional_edges(
            "router",
            self.determine_pipeline_type,
            {
                PipelineType.DOCUMENTATION: "documentation_handler",
                PipelineType.FILE: "file_handler",
                PipelineType.CODE: "code_handler",
                PipelineType.CONVERSATION: "conversation_handler"
            }
        )

        # Handler -> Router/Cleanup edges
        for handler in ["documentation_handler", "file_handler", "code_handler", "conversation_handler"]:
            workflow.add_conditional_edges(
                handler,
                self.should_continue,
                {
                    True: "router",
                    False: "cleanup"
                }
            )

        # Final edge to END
        workflow.add_edge("cleanup", END)

        return workflow.compile()

    # ============= Helper Functions =============
    def initialize_session(self, state: WorkflowState) -> WorkflowState:
        """Initialize the session state"""
        state.operation_stack = []
        state.temporary_storage = {}
        state.should_end = False
        logger.info("Initialized session.")
        return state

    async def cleanup_session(self, state: WorkflowState) -> WorkflowState:
        """Clean up the session state"""
        try:
            # Save any necessary state
            if state.temporary_storage:
                await self._save_temporary_storage(state.temporary_storage)

            # Clear temporary data
            state.temporary_storage = {}
            state.operation_stack = []
            state.should_end = True

            state.messages.append(Message(
                content="Session has been cleaned up.",
                type=MessageType.SYSTEM,
                timestamp=datetime.now()
            ))
            logger.info("Cleaned up session.")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

        return state

    async def _save_temporary_storage(self, temporary_storage: Dict[str, Any]):
        """Save any important temporary data before ending session"""
        # Implement saving logic here
        # For example, write to a file or a database
        logger.info(f"Saving temporary storage: {temporary_storage}")

    def should_continue(self, state: WorkflowState) -> bool:
        """Determine if we should continue processing or end the session"""
        if state.should_end:
            return False

        if len(state.operation_stack) > 10:  # Prevent infinite loops
            logger.warning("Operation stack exceeded limit. Ending session.")
            return False

        if state.current_step.get("force_end", False):
            logger.info("Force ending the session.")
            return False

        return True

    async def route_request(self, state: WorkflowState) -> WorkflowState:
        """Route incoming requests"""
        pipeline = self.determine_pipeline_type(state)
        state.pipeline_type = pipeline
        logger.info(f"Routed to pipeline: {pipeline}")
        return state

    def determine_pipeline_type(self, state: WorkflowState) -> PipelineType:
        """Determine which pipeline to use"""
        if not state.messages:
            return PipelineType.CONVERSATION

        last_message = state.messages[-1].content

        if last_message.startswith(('http://', 'https://')):
            return PipelineType.DOCUMENTATION
        elif any(marker in last_message for marker in ['def ', 'class ', 'import ']):
            return PipelineType.CODE
        elif last_message.startswith(('/file', '/dir')):
            return PipelineType.FILE
        else:
            return PipelineType.CONVERSATION

    # ============= Public Interface =============
    async def process_message(self, message: str, metadata: Dict[str, Any] = None) -> List[str]:
        """Process a message and return responses"""
        new_message = Message(
            content=message,
            type=MessageType.USER,
            timestamp=datetime.now(),
            metadata=metadata or {}
        )
        self.state.messages.append(new_message)
        logger.info(f"Processed user message: {message}")

        updated_state = await self.workflow.run(self.state)
        self.state = updated_state

        # Return all assistant messages since the last user message
        assistant_responses = [
            msg.content for msg in self.state.messages
            if msg.type == MessageType.ASSISTANT and msg.timestamp > new_message.timestamp
        ]

        return assistant_responses

    async def load_documentation(self, url: str, allowed_domains: Optional[List[str]] = None) -> None:
        """Public method to load documentation from a URL"""
        await self.knowledge_base.load_documentation(url, allowed_domains)
        logger.info(f"Documentation loaded from {url}")

    async def load_project(self, path: str) -> None:
        """Public method to load a project into the knowledge base"""
        await self.knowledge_base.load_project(path)
        logger.info(f"Project loaded from {path}")

    async def get_context(self, query: str) -> Dict[str, Any]:
        """Get relevant context from the knowledge base"""
        relevant_entries = {}
        for key, entry in self.knowledge_base.entries.items():
            if self._is_relevant(query, entry.content):
                relevant_entries[key] = entry.content
        logger.info(f"Retrieved context for query: {query}")
        return relevant_entries

    async def analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code with current context"""
        analysis_result = {
            "imports": [],
            "dependencies": [],
            "functions": [],
            "classes": [],
            "potential_issues": []
        }

        try:
            tree = ast.parse(code)
            analysis = self._analyze_ast(tree)
            analysis_result.update(analysis)
            logger.info("Code analysis completed.")
        except SyntaxError as e:
            analysis_result["potential_issues"].append(str(e))
            logger.warning(f"Syntax error during code analysis: {e}")

        return analysis_result

    async def generate_code(self, prompt: str) -> str:
        """Generate code using available context"""
        # Placeholder for code generation logic
        # You can integrate with a language model here
        relevant_context = await self.get_context(prompt)
        # Use the context to generate appropriate code
        generated_code = f"# Generated code based on prompt: {prompt}\n"
        logger.info("Generated code based on prompt.")
        return generated_code

    async def search_documentation(self, query: str) -> List[Dict[str, Any]]:
        """Search loaded documentation"""
        results = []
        for key, entry in self.knowledge_base.entries.items():
            if key.startswith("doc:") and self._is_relevant(query, entry.content):
                relevance = self._calculate_relevance(query, entry.content)
                results.append({
                    "source": key,
                    "content": entry.content,
                    "relevance": relevance
                })
        sorted_results = sorted(results, key=lambda x: x["relevance"], reverse=True)
        logger.info(f"Documentation search completed for query: {query}")
        return sorted_results

    def get_project_structure(self, project_path: str) -> Dict[str, Any]:
        """Get the structure of a loaded project"""
        path = Path(project_path)
        if path not in self.knowledge_base.project_contexts:
            logger.warning(f"Project path not found in knowledge base: {project_path}")
            return {}

        project_context = self.knowledge_base.project_contexts[path]
        structure = {
            "files": list(map(str, project_context.files.keys())),
            "dependencies": project_context.package_dependencies,
            "import_graph": {
                str(k): [str(v) for v in vs]
                for k, vs in project_context.import_graph.items()
            }
        }
        logger.info(f"Retrieved project structure for {project_path}")
        return structure

    # ============= Private Helper Methods =============
    def _is_relevant(self, query: str, content: Any) -> bool:
        """Determine if content is relevant to query"""
        if isinstance(content, str):
            return query.lower() in content.lower()
        elif isinstance(content, dict):
            return any(self._is_relevant(query, v) for v in content.values())
        elif isinstance(content, (list, tuple, set)):
            return any(self._is_relevant(query, item) for item in content)
        return False

    def _calculate_relevance(self, query: str, content: Any) -> float:
        """Calculate relevance score between query and content"""
        if isinstance(content, str):
            query_words = set(query.lower().split())
            content_words = set(content.lower().split())
            intersection = query_words & content_words
            if not query_words:
                return 0.0
            return len(intersection) / len(query_words)
        return 0.0

    def _analyze_ast(self, tree: ast.AST) -> Dict[str, Any]:
        """Analyze Python AST"""
        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
        }

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                analysis["imports"].extend(name.name for name in node.names)
            elif isinstance(node, ast.ImportFrom):
                analysis["imports"].append(f"{node.module}")
            elif isinstance(node, ast.FunctionDef):
                analysis["functions"].append(node.name)
            elif isinstance(node, ast.ClassDef):
                analysis["classes"].append(node.name)

        return analysis
