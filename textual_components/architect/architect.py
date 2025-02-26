from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, Container, ScrollableContainer
from textual.widgets import Static, Input, Button, Tree, Label, Footer
from textual.reactive import reactive
from textual.widgets.tree import TreeNode
from textual import events
from rich.syntax import Syntax
from rich.text import Text

from ..architect.tab_button import TabButton
from ..architect.file_tree import FileExplorer

class Architect(App):
    """A textual app that mimics a code editor."""

    CSS = """
    Screen {
        background: #1e1e1e;
    }

    FileExplorer {
        width: 25%;
        background: #252526;
        border-right: solid #3c3c3c;
    }

    #editor-area {
        width: 1fr;
    }

    #assistant-panel {
        width: 30%;
        background: #252526;
        border-left: solid #3c3c3c;
    }

    #explorer-header {
        height: 2;
        background: #252526;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }

    #explorer-search {
        margin: 0 1;
    }

    #tabs-bar {
        height: 3;
        background: #252526;
        border-bottom: solid #3c3c3c;
    }

    #breadcrumb-bar {
        height: 2;
        background: #252526;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }

    #status-bar {
        height: 1;
        background: #252526;
        border-top: solid #3c3c3c;
        padding: 0 1;
    }

    #assistant-header {
        height: 2;
        background: #252526;
        border-bottom: solid #3c3c3c;
        padding: 0 1;
    }

    #assistant-input {
        margin: 0 1 1 1;
    }

    #code-view {
        padding: 1;
    }

    .tab-button {
        background: #2d2d2d;
        color: #cccccc;
        padding: 0 2;
        border-right: solid #3c3c3c;
    }

    .tab-button:hover {
        background: #383838;
    }

    .active-tab {
        background: #1e1e1e;
        color: #ffffff;
    }

    .breadcrumb {
        color: #cccccc;
    }

    Button.icon {
        min-width: 4;
        padding: 0 1;
    }
    #code-content {
        width: 100%;
        height: auto;
        padding: 1;
    }

    #code-view {
        height: 1fr;
        background: #1e1e1e;
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

            # Mark the current tab as active
            if self.current_file and tab['name'] == self.current_file['name']:
                tab_button.add_class("active-tab")

            tab_button.add_class("tab-button")
            tabs_container.mount(tab_button)


    def update_editor(self):
        """Update the editor content."""
        # Get the Static widget inside the ScrollableContainer
        code_view = self.query_one("#code-content")

        if not self.current_file:
            code_view.update("Select a file to view its content")
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

        # Update code view
        content = self.current_file.get('content', 'No content')
        language = self.current_file.get('language', 'text')

        # Use rich's Syntax for syntax highlighting
        syntax = Syntax(content, language, theme="monokai", line_numbers=True)
        code_view.update(syntax)

    def compose(self) -> ComposeResult:
        """Create child widgets."""
        # Main layout - Horizontal split
        with Horizontal():
            # File Explorer Panel
            with Vertical():
                with Container(id="explorer-header"):
                    yield Label("EXPLORER", id="explorer-title")
                yield Input(placeholder="Search files...", id="explorer-search")
                yield FileExplorer(files=self.mock_files, id="file-explorer")

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
                    yield Static("Select a file to view its content", id="code-content")

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

if __name__ == "__main__":
    app = Architect()
    app.run()
