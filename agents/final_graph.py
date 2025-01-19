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

class Splatter:
    output_log: CustomRichLog
    def __init__(self):
        # Initialize core components
        self.state = None
        self.workflow = None
        self.knowledge_base = None
        self.initialize_components()

    def initialize_components(self):
        """Initialize all core components"""
        self.knowledge_base = self.EnhancedKnowledgeBase()
        self.state = self.WorkflowState(knowledge_base=self.knowledge_base)
        self.workflow = self.create_workflow_graph()

    # ============= Core State Classes =============
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
        type: 'Splatter.MessageType'
        timestamp: datetime
        metadata: Dict[str, Any] = None

    # ============= Knowledge Management =============
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

    # ============= Context Management =============
    class ProjectContext:
        def __init__(self, root_dir: Path):
            self.root_dir = root_dir
            self.files: Dict[Path, 'Splatter.FileNode'] = {}
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
            with open(file_path) as f:
                content = f.read()
            file_node = Splatter.FileNode(str(file_path), content)
            self.files[file_path] = file_node
            await self.analyze_file_dependencies(file_node)

        async def analyze_file_dependencies(self, file_node: 'Splatter.FileNode'):
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

            except SyntaxError:
                pass

        async def resolve_dependencies(self, file_node: 'Splatter.FileNode'):
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
                    if importlib.util.find_spec(import_name.split('.')[0]):
                        self.package_dependencies[import_name.split('.')[0]] = "unknown"

    class WebScraper:
        def __init__(self):
            self.visited_urls: Set[str] = set()
            self.session = requests.Session()
            self.max_depth = 3

        async def scrape_documentation(self, base_url: str, allowed_domains: Optional[List[str]] = None) -> Dict[str, 'Splatter.WebContent']:
            content_map = {}
            base_domain = urlparse(base_url).netloc
            allowed_domains = allowed_domains or [base_domain]

            await self._scrape_url(base_url, content_map, allowed_domains, depth=0)
            return content_map

        async def _scrape_url(self, url: str, content_map: Dict[str, 'Splatter.WebContent'], allowed_domains: List[str], depth: int):
            if depth >= self.max_depth or url in self.visited_urls:
                return

            if not any(domain in url for domain in allowed_domains):
                return

            try:
                response = self.session.get(url)
                soup = BeautifulSoup(response.text, 'html.parser')

                content = self._extract_main_content(soup)
                metadata = self._extract_metadata(soup)

                web_content = Splatter.WebContent(url, content, metadata)
                content_map[url] = web_content
                self.visited_urls.add(url)

                for link in soup.find_all('a', href=True):
                    next_url = urljoin(url, link['href'])
                    if next_url not in self.visited_urls:
                        web_content.related_urls.add(next_url)
                        await self._scrape_url(next_url, content_map, allowed_domains, depth + 1)

            except Exception as e:
                print(f"Error scraping {url}: {e}")

        def _extract_main_content(self, soup: BeautifulSoup) -> str:
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                return main_content.get_text(strip=True)
            return soup.get_text(strip=True)

        def _extract_metadata(self, soup: BeautifulSoup) -> Dict[str, Any]:
            return {
                'title': soup.title.string if soup.title else None,
                'meta_description': soup.find('meta', {'name': 'description'})['content'] if soup.find('meta', {'name': 'description'}) else None,
                'h1': [h1.get_text(strip=True) for h1 in soup.find_all('h1')],
            }

    class EnhancedKnowledgeBase:
        def __init__(self):
            self.entries: Dict[str, 'Splatter.KnowledgeEntry'] = {}
            self.web_scraper = Splatter.WebScraper()
            self.project_contexts: Dict[Path, 'Splatter.ProjectContext'] = {}
            self.max_size = 1000

        async def add_entry(self, key: str, content: Any, source: str):
            """Add an entry to the knowledge base"""
            if len(self.entries) >= self.max_size:
                self._cleanup()
            self.entries[key] = Splatter.KnowledgeEntry(
                content=content,
                source=source,
                timestamp=datetime.now()
            )

        def get_entry(self, key: str) -> Optional[Any]:
            """Get an entry from the knowledge base"""
            if key in self.entries:
                entry = self.entries[key]
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

        async def load_documentation(self, url: str, allowed_domains: Optional[List[str]] = None):
            """Load documentation from a URL"""
            content_map = await self.web_scraper.scrape_documentation(url, allowed_domains)

            for url, web_content in content_map.items():
                await self.add_entry(
                    f"doc:{url}",
                    web_content,
                    source="web_documentation"
                )

        async def load_project(self, root_dir: str):
            """Load a project into the knowledge base"""
            root_path = Path(root_dir)
            if root_path not in self.project_contexts:
                self.project_contexts[root_path] = Splatter.ProjectContext(root_path)

            project_context = self.project_contexts[root_path]
            await project_context.process_project()

    class WorkflowState(BaseModel):
        messages: List['Splatter.Message'] = []
        knowledge_base: 'Splatter.EnhancedKnowledgeBase'
        pipeline_type: Optional['Splatter.PipelineType'] = None
        current_step: Dict[str, Any] = {}
        operation_stack: List[str] = []
        temporary_storage: Dict[str, Any] = {}
        should_end: bool = False

        class Config:
            arbitrary_types_allowed = True

    # ============= Pipeline Handlers =============
    async def handle_documentation(self, state: WorkflowState) -> WorkflowState:
        """Handle documentation loading requests"""
        try:
            state.operation_stack.append("documentation_loading")
            url = state.messages[-1].content
            await state.knowledge_base.load_documentation(url)

            state.messages.append(self.Message(
                content=f"Documentation from {url} has been loaded",
                type=self.MessageType.SYSTEM,
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
            await state.knowledge_base.load_project(path)

            state.messages.append(self.Message(
                content=f"Loaded project from {path}",
                type=self.MessageType.SYSTEM,
                timestamp=datetime.now()
            ))

        finally:
            state.operation_stack.pop()

        return state

    async def handle_code(self, state: WorkflowState) -> WorkflowState:
        """Handle code operations"""
        try:
            state.operation_stack.append("code_operation")
            # Add your code handling logic here

        finally:
            state.operation_stack.pop()

        return state

    async def handle_conversation(self, state: WorkflowState) -> WorkflowState:
        """Handle conversation"""
        try:
            state.operation_stack.append("conversation")
            # Add your conversation handling logic here

        finally:
            state.operation_stack.pop()

        return state

    # ============= Graph Creation =============
    def create_workflow_graph(self):
        """Create the workflow graph with proper start and end conditions"""
        workflow = StateGraph(self.WorkflowState)

        # Add entry point node
        workflow.add_node("start", self.initialize_session)

        # Add main nodes
        workflow.add_node("router", self.route_request)
        workflow.add_node("documentation_handler", self.handle_documentation)
        workflow.add_node("file_handler", self.handle_files)
        workflow.add_node("code_handler", self.handle_code)
        workflow.add_node("conversation_handler", self.handle_conversation)

        # Add cleanup/end node
        workflow.add_node("cleanup", self.cleanup_session)

        # Start -> Router edge
        workflow.add_edge("start", "router")

        # Router -> Handler edges
        workflow.add_conditional_edges(
            "router",
            self.determine_pipeline_type,
            {
                self.PipelineType.DOCUMENTATION: "documentation_handler",
                self.PipelineType.FILE: "file_handler",
                self.PipelineType.CODE: "code_handler",
                self.PipelineType.CONVERSATION: "conversation_handler"
            }
        )

        # Handler -> Cleanup/Router edges
        for node in ["documentation_handler", "file_handler", "code_handler", "conversation_handler"]:
            workflow.add_conditional_edges(
                node,
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
    async def initialize_session(self, state: WorkflowState) -> WorkflowState:
        """Initialize the session state"""
        state.operation_stack = []
        state.temporary_storage = {}
        state.should_end = False
        return state

    async def cleanup_session(self, state: WorkflowState) -> WorkflowState:
        """Clean up the session state"""
        # Save any necessary state
        if state.temporary_storage:
            await self._save_temporary_storage(state.temporary_storage)

        # Clear temporary data
        state.temporary_storage = {}
        state.operation_stack = []
        state.should_end = True
        return state

    async def _save_temporary_storage(self, temporary_storage: Dict[str, Any]):
        """Save any important temporary data before ending session"""
        # Implement saving logic here
        pass

    def should_continue(self, state: WorkflowState) -> bool:
        """Determine if we should continue processing or end the session"""
        # Check various conditions to determine if we should continue
        if state.should_end:
            return False

        if len(state.operation_stack) > 10:  # Prevent infinite loops
            return False

        if state.current_step.get("force_end", False):
            return False

        return True

    async def route_request(self, state: WorkflowState) -> WorkflowState:
        """Route incoming requests"""
        state.pipeline_type = self.determine_pipeline_type(state)
        return state

    def determine_pipeline_type(self, state: WorkflowState) -> PipelineType:
        """Determine which pipeline to use"""
        if not state.messages:
            return self.PipelineType.CONVERSATION

        last_message = state.messages[-1].content

        if last_message.startswith(('http://', 'https://')):
            return self.PipelineType.DOCUMENTATION
        elif any(marker in last_message for marker in ['def ', 'class ', 'import ']):
            return self.PipelineType.CODE
        elif last_message.startswith(('/file', '/dir')):
            return self.PipelineType.FILE
        else:
            return self.PipelineType.CONVERSATION

    def should_end(self, state: WorkflowState) -> bool:
        """Determine if the workflow should end"""
        return state.should_end or len(state.operation_stack) == 0

    # ============= Public Interface =============
    async def process_message(self, message: str, metadata: Dict[str, Any] = None) -> List[str]:
        """Process a message and return responses"""
        self.state.messages.append(self.Message(
            content=message,
            type=self.MessageType.USER,
            timestamp=datetime.now(),
            metadata=metadata
        ))

        updated_state = await self.workflow.run(self.state)
        self.state = updated_state

        # Return all assistant messages since the last user message
        return [msg.content for msg in self.state.messages
                if msg.type == self.MessageType.ASSISTANT]

    async def load_documentation(self, url: str) -> None:
        """Load documentation from a URL"""
        await self.knowledge_base.load_documentation(url)

    async def load_project(self, path: str) -> None:
            """Load a project into the knowledge base"""
            await self.knowledge_base.load_project(path)

    async def get_context(self, query: str) -> Dict[str, Any]:
        """Get relevant context from the knowledge base"""
        # Implement context retrieval logic here
        relevant_entries = {}
        for key, entry in self.knowledge_base.entries.items():
            if self._is_relevant(query, entry.content):
                relevant_entries[key] = entry.content
        return relevant_entries

    async def analyze_code(self, code: str) -> Dict[str, Any]:
        """Analyze code with current context"""
        analysis_result = {
            "imports": [],
            "dependencies": [],
            "structure": {},
            "potential_issues": []
        }

        try:
            tree = ast.parse(code)
            analysis_result.update(self._analyze_ast(tree))
        except SyntaxError as e:
            analysis_result["potential_issues"].append(str(e))

        return analysis_result

    async def generate_code(self, prompt: str) -> str:
        """Generate code using available context"""
        # Implement code generation logic here
        relevant_context = await self.get_context(prompt)
        # Use the context to generate appropriate code
        return "# Generated code would go here"

    async def search_documentation(self, query: str) -> List[Dict[str, Any]]:
        """Search loaded documentation"""
        results = []
        for key, entry in self.knowledge_base.entries.items():
            if key.startswith("doc:") and self._is_relevant(query, entry.content):
                results.append({
                    "source": key,
                    "content": entry.content,
                    "relevance": self._calculate_relevance(query, entry.content)
                })
        return sorted(results, key=lambda x: x["relevance"], reverse=True)

    def get_project_structure(self, project_path: str) -> Dict[str, Any]:
        """Get the structure of a loaded project"""
        path = Path(project_path)
        if path not in self.knowledge_base.project_contexts:
            return {}

        project_context = self.knowledge_base.project_contexts[path]
        return {
            "files": list(map(str, project_context.files.keys())),
            "dependencies": project_context.package_dependencies,
            "import_graph": {
                str(k): [str(v) for v in vs]
                for k, vs in project_context.import_graph.items()
            }
        }

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
        # Implement more sophisticated relevance calculation
        if isinstance(content, str):
            return len(set(query.lower().split()) & set(content.lower().split())) / len(set(query.lower().split()))
        return 0.0

    def _analyze_ast(self, tree: ast.AST) -> Dict[str, Any]:
        """Analyze Python AST"""
        analysis = {
            "imports": [],
            "functions": [],
            "classes": [],
            "complexity": 0
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

    @classmethod
    async def create_and_initialize(cls, config: Dict[str, Any] = None) -> 'Splatter':
        """Create and initialize a Splatter instance"""
        instance = cls()
        if config:
            # Configure the instance based on provided config
            pass
        return instance
