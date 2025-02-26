from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Static, Input, Button, Tree, Label, Footer
from textual.widget import Widget
from textual.reactive import reactive
from textual.widgets.tree import TreeNode
from textual import events
from rich.syntax import Syntax
from rich.text import Text

from ..architect.tab_button import TabButton
from ..architect.file_tree import FileExplorer
from .code_editor import CodeEditor
from collections import deque
from pathlib import Path
import os
import fnmatch
import mimetypes

class Architect(Widget):
    """A textual app that mimics a code editor."""

    """A textual app that mimics a code editor."""

    DEFAULT_CSS = """
    /* Namespace all styles under .architect-container to prevent conflicts */
    .architect-container {
        background: #1e1e1e;
        width: 100%;
        height: 100%;
        layout: horizontal;  /* Ensure horizontal layout */
    }

    .architect-container FileExplorer {
        width: 25%;
        background: #252526;
        border-right: solid #3c3c3c;
    }

    .architect-container #editor-area {
        width: 1fr;
    }

    .architect-container #assistant-panel {
        width: 30%;
        background: #252526;
        border-left: solid #3c3c3c;
    }

    .architect-container #explorer-header {
        height: 2;
        background: #252526;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }

    .architect-container #explorer-search {
        margin: 0 1;
    }

    /* Continue namespacing all other CSS rules... */
    .architect-container #tabs-bar {
        height: 3;
        background: #252526;
        border-bottom: solid #3c3c3c;
    }

    .architect-container #breadcrumb-bar {
        height: 2;
        background: #252526;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }

    .architect-container #status-bar {
        height: 1;
        background: #252526;
        border-top: solid #3c3c3c;
        padding: 0 1;
    }

    .architect-container #assistant-header {
        height: 2;
        background: #252526;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }

    .architect-container #assistant-input {
        margin: 0 1 1 1;
    }

    .architect-container #code-view {
        padding: 1;
    }

    .architect-container .tab-button {
        background: #2d2d2d;
        color: #cccccc;
        padding: 0 2;
        border-right: solid #3c3c3c;
    }

    .architect-container .tab-button:hover {
        background: #383838;
    }

    .architect-container .active-tab {
        background: #1e1e1e;
        color: #ffffff;
    }

    .architect-container .breadcrumb {
        color: #cccccc;
    }

    .architect-container Button.icon {
        min-width: 4;
        padding: 0 1;
    }

    .architect-container #code-content {
        width: 100%;
        height: auto;
        padding: 1;
    }

    .architect-container #code-view {
        height: 1fr;
        background: #1e1e1e;
    }

    .tab-button.modified {
        /* Base style for modified tabs */
    }

    .tab-button.modified .dot {
        color: rgb(150, 150, 150);  /* Light gray dot */
    }
    """

    is_assistant_open = reactive(True)
    current_file = reactive(None)
    open_tabs = reactive([])

    BINDINGS = [
        ("ctrl+b", "toggle_explorer", "Toggle Explorer"),
        ("ctrl+j", "toggle_assistant", "Toggle Assistant"),
        ("ctrl+w", "close_tab", "Close Tab"),
    ]

    def __init__(self):
        super().__init__()
        self.mock_files = [
            {
                "name": "src",
                "type": "folder",
                "children": [
                    {
                        "name": "components",
                        "type": "folder",
                        "children": [
                            {"name": "Header.tsx", "type": "file", "language": "typescript", "content": "import React from 'react'\n\nexport const Header = () => {\n  return (\n    <header className=\"bg-gray-800 text-white p-4\">\n      <h1>My App</h1>\n    </header>\n  )\n}"},
                            {"name": "Footer.tsx", "type": "file", "language": "typescript", "content": "import React from 'react'\n\nexport const Footer = () => {\n  return (\n    <footer className=\"bg-gray-800 text-white p-4\">\n      <p>© 2023 My App</p>\n    </footer>\n  )\n}"},
                        ],
                    },
                    {"name": "App.tsx", "type": "file", "language": "typescript", "content": "import React from 'react'\n\nexport default function App() {\n  return (\n    <div className=\"min-h-screen bg-zinc-900\">\n      <h1>Hello World</h1>\n    </div>\n  )\n}"},
                    {"name": "index.css", "type": "file", "language": "css", "content": "body {\n  margin: 0;\n  padding: 0;\n  font-family: sans-serif;\n}\n\n.container {\n  max-width: 1200px;\n  margin: 0 auto;\n  padding: 0 1rem;\n}"},
                ],
            },
            {
                "name": "public",
                "type": "folder",
                "children": [
                    {"name": "index.html", "type": "file", "language": "html", "content": "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n  <meta charset=\"UTF-8\">\n  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n  <title>My App</title>\n</head>\n<body>\n  <div id=\"root\"></div>\n</body>\n</html>"},
                    {"name": "favicon.ico", "type": "file", "content": "Binary file content..."},
                ],
            },
            {"name": "package.json", "type": "file", "language": "json", "content": "{\n  \"name\": \"my-app\",\n  \"version\": \"0.1.0\",\n  \"private\": true,\n  \"dependencies\": {\n    \"react\": \"^18.2.0\",\n    \"react-dom\": \"^18.2.0\"\n  }\n}"},
            {"name": "tsconfig.json", "type": "file", "language": "json", "content": "{\n  \"compilerOptions\": {\n    \"target\": \"es5\",\n    \"lib\": [\"dom\", \"dom.iterable\", \"esnext\"],\n    \"allowJs\": true,\n    \"skipLibCheck\": true,\n    \"esModuleInterop\": true,\n    \"strict\": true,\n    \"forceConsistentCasingInFileNames\": true,\n    \"noFallthroughCasesInSwitch\": true,\n    \"module\": \"esnext\",\n    \"moduleResolution\": \"node\",\n    \"resolveJsonModule\": true,\n    \"isolatedModules\": true,\n    \"noEmit\": true,\n    \"jsx\": \"react-jsx\"\n  },\n  \"include\": [\"src\"]\n}"},
        ]
        self.file_structure = self.scan_directory(os.getcwd())

    def action_toggle_explorer(self) -> None:
        """Toggle file explorer visibility."""
        # This would need additional implementation
        self.notify("Toggle Explorer not implemented yet")

    def action_toggle_assistant(self) -> None:
        """Toggle assistant panel visibility."""
        self.is_assistant_open = not self.is_assistant_open
        assistant_panel = self.query_one("#assistant-panel")
        assistant_panel.display = assistant_panel.display != "none"

    def action_close_tab(self) -> None:
        """Close the current tab."""
        if not self.open_tabs:
            return

        # Find the current tab index
        current_idx = next((i for i, tab in enumerate(self.open_tabs)
                            if tab['name'] == self.current_file['name']), None)

        if current_idx is not None:
            # Remove the tab
            removed = self.open_tabs.pop(current_idx)

            # Update the tabs UI
            self.update_tabs()

            # Open a different tab if available
            if self.open_tabs:
                next_idx = min(current_idx, len(self.open_tabs) - 1)
                self.open_file(self.open_tabs[next_idx])
            else:
                # No tabs left, clear the editor
                self.current_file = None
                self.update_editor()

    def open_file(self, file_data):
        """Open a file in the editor."""
        self.current_file = file_data

        # Add to tabs if not already open
        if not any(tab['name'] == file_data['name'] for tab in self.open_tabs):
            self.open_tabs.append(file_data)
            self.update_tabs()

        self.update_editor()

    def update_tabs(self):
        """Update the tabs display."""
        tabs_container = self.query_one("#tabs-container")
        tabs_container.remove_children()
        
        for tab in self.open_tabs:
            tab_button = TabButton(
                f"{tab['name']} ✕",
                tab,
                close_callback=self.action_close_tab
            )
            tabs_container.mount(tab_button)

    def on_code_change(self, content: str) -> None:
        """Save changes when code is modified."""
        if self.current_file:
            self.current_file['content'] = content
            # You might want to add file saving logic here
            # For example:
            # with open(self.current_file['path'], 'w') as f:
            #     f.write(content)

    def on_file_save(self) -> None:
        """Save the current file to disk."""
        if self.current_file and self.current_file.get('path'):
            try:
                with open(self.current_file['path'], 'w') as f:
                    f.write(self.current_file['content'])
                self.current_file['modified'] = False
                self.update_tabs()
                self.notify(f"Saved: {self.current_file['name']}")
            except Exception as e:
                self.notify(f"Error saving file: {str(e)}", severity="error")

    def update_editor(self):
        """Update the editor content."""
        # Get the CodeEditor widget
        code_editor = self.query_one("#code-content", CodeEditor)

        if not self.current_file:
            code_editor.text = "Select a file to view its content"
            code_editor._last_saved_content = "Select a file to view its content"
            self.query_one("#breadcrumb-container").update("")
            self.query_one("#status-bar-content").update("")
            return

        # Update breadcrumb
        path_parts = []
        if self.current_file['name'] == "App.tsx":
            path_parts = ["src", "App.tsx"]
        elif self.current_file['name'] in ["Header.tsx", "Footer.tsx"]:
            path_parts = ["src", "components", self.current_file['name']]
        else:
            # Simple fallback
            path_parts = [self.current_file['name']]

        breadcrumb_text = " > ".join(path_parts)
        self.query_one("#breadcrumb-container").update(breadcrumb_text)

        # Update status bar
        language = self.current_file.get('language', 'plain')
        status_text = f"main   {language.capitalize()}   UTF-8   Ln 1, Col 1"
        self.query_one("#status-bar-content").update(status_text)

        # Update the editor content
        content = self.current_file.get('content', 'No content')
        code_editor.text = content
        
        # If the file is not marked as modified, update the last saved content
        if not self.current_file.get('modified', False):
            code_editor._last_saved_content = content

    def compose(self) -> ComposeResult:
            """Create child widgets."""
            # Wrap everything in a container with the namespace class
            with Container(classes="architect-container"):
                # Main layout - Horizontal split
                with Horizontal():
                    # File Explorer Panel
                    with Vertical():
                        with Container(id="explorer-header"):
                            yield Label("EXPLORER", id="explorer-title")
                        yield Input(placeholder="Search files...", id="explorer-search")
                        yield FileExplorer(files=self.file_structure, architect=self,id="file-explorer")
                    # Editor Area
                    with Vertical(id="editor-area"):
                        # Tabs Bar
                        with Container(id="tabs-bar"):
                            yield Horizontal(id="tabs-container")

                        # Breadcrumb Bar
                        with Container(id="breadcrumb-bar"):
                            yield Static(id="breadcrumb-container", classes="breadcrumb")

                        # Editor Content
                        with ScrollableContainer(id="code-view"):
                            yield CodeEditor(
                                "Select a file to view its content", 
                                id="code-content",
                                on_change=self.on_code_change
                            )

                        # Status Bar
                        with Container(id="status-bar"):
                            yield Static(id="status-bar-content")

                    # Assistant Panel
                    with Vertical(id="assistant-panel"):
                        with Container(id="assistant-header"):
                            yield Label("AI ASSISTANT", id="assistant-title")

                        with ScrollableContainer(id="assistant-messages"):
                            yield Static("I can help you with coding tasks. Ask me anything!")

                        yield Input(placeholder="Ask a question...", id="assistant-input")

                yield Footer()

    def scan_directory(self, directory_path, ignore_dirs=None, ignore_files=None, max_file_size=500*1024):
        """
        Scan a directory and create a hierarchical structure of files and folders.

        Args:
            directory_path (str): Path to the directory to scan
            ignore_dirs (set): Set of directory names to ignore
            ignore_files (set): Set of file patterns to ignore
            max_file_size (int): Maximum file size to read content (in bytes)

        Returns:
            list: A list of dictionaries representing the directory structure
        """
        if ignore_dirs is None:
            ignore_dirs = {
                '.git', '.svn', '.hg', 'node_modules', '__pycache__',
                '.venv', 'venv', 'env', 'dist', 'build', '.next',
                '.idea', '.vscode', '.pytest_cache', '.mypy_cache'
            }

        if ignore_files is None:
            ignore_files = {
                '*.pyc', '*.pyo', '*.dll', '*.obj', '*.o', '*.a', '*.lib',
                '*.so', '*.dylib', '*.ncb', '*.sdf', '*.suo', '*.pdb',
                '*.idb', '.DS_Store', '*.class', '*.psd', '*.db', '*.jpg',
                '*.jpeg', '*.png', '*.gif', '*.svg', '*.eot', '*.ttf',
                '*.woff', '*.mp4', '*.mp3', '*.lock', 'package-lock.json'
            }

        result = []

        try:
            entries = sorted(os.listdir(directory_path))

            for entry in entries:
                full_path = os.path.join(directory_path, entry)

                # Skip if the entry should be ignored
                if os.path.isdir(full_path) and entry in ignore_dirs:
                    continue

                if os.path.isfile(full_path) and any(
                    fnmatch.fnmatch(entry, pattern) for pattern in ignore_files
                ):
                    continue

                if os.path.isdir(full_path):
                    # Recursively scan subdirectory
                    children = self.scan_directory(full_path, ignore_dirs, ignore_files, max_file_size)
                    if children:  # Only add non-empty directories
                        result.append({
                            "name": entry,
                            "type": "folder",
                            "children": children
                        })
                else:
                    # Process file
                    try:
                        file_data = {"name": entry, "type": "file"}

                        # Add language info if we can detect it
                        language = self.detect_language(full_path)
                        if language:
                            file_data["language"] = language

                        # Only read content if it's not a binary file and not too large
                        if not self.is_binary_file(full_path):
                            stat_info = os.stat(full_path)
                            if stat_info.st_size <= max_file_size:
                                try:
                                    with open(full_path, 'r', encoding='utf-8') as f:
                                        file_data["content"] = f.read()
                                except UnicodeDecodeError:
                                    file_data["content"] = "Binary file content..."
                            else:
                                file_data["content"] = f"File too large ({stat_info.st_size} bytes)..."
                        else:
                            file_data["content"] = "Binary file content..."

                        result.append(file_data)
                    except Exception as e:
                        # If there's an error reading the file, include a note
                        result.append({
                            "name": entry,
                            "type": "file",
                            "error": str(e)
                        })
        except PermissionError:
            # If we can't access the directory, just return it as inaccessible
            return []
        except Exception as e:
            # Handle unexpected errors
            print(f"Error scanning {directory_path}: {e}")
            return []

        return result

    def scan_project_directory(self, start_path=None, max_file_size=500*1024):
        """
        Scan a project directory and return the file structure
        """
        import fnmatch

        # If no path is provided, use the current directory
        if start_path is None:
            start_path = os.getcwd()

        # Define ignore patterns
        ignore_dirs = {
            # Version Control
            '.git', '.svn', '.hg', '.bzr',

            # Python
            '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache',
            'venv', '.venv', 'env', '.env', '.tox',

            # Node.js / JavaScript
            'node_modules', 'bower_components',
            '.next', '.nuxt', '.gatsby',

            # Build directories
            'dist', 'build', '_build', 'public/build',
            'target', 'out', 'output',
            'bin', 'obj',

            # IDE and editors
            '.idea', '.vscode', '.vs',
            '.settings', '.project', '.classpath',

            # Dependencies
            'vendor', 'packages',

            # Coverage and tests
            'coverage', '.coverage', 'htmlcov',

            # Mobile
            'Pods', '.gradle',

            # Misc
            'tmp', 'temp', 'logs',
            '.sass-cache', '.parcel-cache',
            '.cargo', 'artifacts'
        }

        ignore_files = {
            # Python
            '*.pyc', '*.pyo', '*.pyd',
            '*.so', '*.egg', '*.egg-info',

            # JavaScript/Web
            '*.min.js', '*.min.css',
            '*.chunk.js', '*.chunk.css',
            '*.bundle.js', '*.bundle.css',
            '*.hot-update.*',

            # Build artifacts
            '*.o', '*.obj', '*.a', '*.lib',
            '*.dll', '*.dylib', '*.so',
            '*.exe', '*.bin',

            # Logs and databases
            '*.log', '*.logs',
            '*.sqlite', '*.sqlite3', '*.db',
            '*.mdb', '*.ldb',

            # Package locks
            'package-lock.json', 'yarn.lock',
            'poetry.lock', 'Pipfile.lock',
            'pnpm-lock.yaml', 'composer.lock',

            # Environment and secrets
            '.env', '.env.*', '*.env',
            '.env.local', '.env.development',
            '.env.test', '.env.production',
            '*.pem', '*.key', '*.cert',

            # Cache files
            '.DS_Store', 'Thumbs.db',
            '*.cache', '.eslintcache',
            '*.swp', '*.swo',

            # Documentation build
            '*.pdf', '*.doc', '*.docx',

            # Images and large media
            '*.jpg', '*.jpeg', '*.png', '*.gif',
            '*.ico', '*.svg', '*.woff', '*.woff2',
            '*.ttf', '*.eot', '*.mp4', '*.mov',

            # Archives
            '*.zip', '*.tar', '*.gz', '*.rar',

            # Generated sourcemaps
            '*.map', '*.css.map', '*.js.map'
        }

        # Start scanning from the directory
        result = self.scan_directory(start_path, ignore_dirs, ignore_files, max_file_size)

        return result


    def detect_language(self, file_path):
        """Detect the programming language based on file extension"""
        extension = Path(file_path).suffix.lower()
        language_map = {
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.py': 'python',
            '.html': 'html',
            '.css': 'css',
            '.scss': 'scss',
            '.json': 'json',
            '.md': 'markdown',
            '.go': 'go',
            '.rs': 'rust',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.rb': 'ruby',
            '.php': 'php',
            '.sh': 'shell',
            '.yaml': 'yaml',
            '.yml': 'yaml',
        }
        return language_map.get(extension, None)

    def is_binary_file(self, file_path):
        """Check if a file is binary"""
        mime_type, _ = mimetypes.guess_type(file_path)
        if mime_type is None:
            # Read the first chunk of the file to check for binary content
            try:
                with open(file_path, 'rb') as f:
                    chunk = f.read(1024)
                    return b'\0' in chunk
            except:
                return True
        return mime_type.startswith(('image/', 'audio/', 'video/', 'application/')) and not mime_type.endswith(('json', 'xml', 'javascript', 'html'))

    def on_mount(self):
        """Handle app start."""
        # Open App.tsx by default
        app_file = next((
            file for folder in self.mock_files
            if folder["name"] == "src"
            for file in folder["children"]
            if file["name"] == "App.tsx"
        ), None)

        if app_file:
            self.open_file(app_file)

    def trigger_completion(self) -> None:
        """Request code completions from an AI agent.
        
        TO_DO
        """
        context = self.get_current_context()
        # This would be asynchronous in a real implementation
        # You'd send the context to your AI and receive suggestions back
        self.app.call_later(self.show_completion_suggestions, ["suggestion1", "suggestion2"])

    def show_completion_suggestions(self, suggestions: list[str]) -> None:
        """Display a popup with code completion suggestions.
        
        TO_DO
        """
        # Create and show a popup with suggestions
        # When a suggestion is selected, call insert_completio

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        button_id = event.button.id
        
        # Handle tab buttons
        if button_id and button_id.startswith("tab-"):
            try:
                # Extract the index from the tab ID
                tab_index = int(button_id.split("-")[1])
                if 0 <= tab_index < len(self.open_tabs):
                    self.current_file = self.open_tabs[tab_index]
                    self.update_editor()
            except (ValueError, IndexError):
                # Handle potential conversion errors
                pass
