from textual.widget import Widget
from textual.widgets import TextArea, Button, Input, OptionList, ContentSwitcher, Static, Label, ListView, ListItem, Header
from textual.widgets.option_list import Option
from textual.app import ComposeResult
from textual.containers import ScrollableContainer, Vertical, Horizontal, VerticalScroll, Container
from textual.binding import Binding
from textual.message import Message
from textual.reactive import var, reactive
from textual import on, events, work
from textual.events import Key
from textual.worker import Worker, WorkerState
from textual import work



from langchain.schema import BaseMessage, HumanMessage, AIMessage
from langchain.prompts import ChatPromptTemplate
from langchain_groq import ChatGroq
from pydantic import SecretStr

from textual_components.architect.input_area import ChatInputArea
from textual_components.architect.graph import ArchitectModel, CodeFile, code_gen_prompt
from textual_components.architect.code_diff import ApplyChangesWidget

import os
class AssistantPanel(Widget):
    DEFAULT_CSS = """
        AssistantPanel {
            layout: vertical;
            height: 100%;
        }

        #assistant-header {
            height: auto;
            margin-bottom: 1;
        }

        #assistant-messages {
            height: 1fr;  /* Take available space */
            margin-bottom: 1;
        }

        #files-loaded {
            height: auto;  /* Automatically size based on content */
            max-height: 15%;  /* But don't take more than 30% of the panel */
            border-top: solid $panel;
            padding: 1;
            overflow-y: scroll;
        }

        #files-loaded-header {
            height: auto;
            margin-bottom: 1;
            color: $text-muted;
        }

        #files-list {
            height: auto;  /* Automatically size based on content */
            margin-bottom: 1;
        }

        #assistant-input {
            height: auto;
            dock: bottom;
            margin-top: 1;
        }
        """
    loaded_files = reactive([])
    def __init__(self, llm):
        super().__init__()
        api_key = os.getenv('GROQ_API_KEY')
        if not api_key:
            raise ValueError("GROQ_API_KEY environment variable is not set")
        # Initialize the LLM
        self.llm = llm

        self.architect_model = ArchitectModel(code_files=None)


    def compose(self):
        with Container(id="assistant-header"):
            yield Label("AI ASSISTANT", id="assistant-title")

        with ScrollableContainer(id="assistant-messages"):
            self.output = TextArea()
            yield self.output
        #yield Input(placeholder="Ask a question...", id="assistant-input")
        with Container(id="files-loaded"):
            yield Static(content="Files in the LLM context")
            with ScrollableContainer():
                self.list_view = ListView()
                yield self.list_view
        yield ChatInputArea(id="assistant-input")

    def add_file_to_loaded_files(self, file_data):
        #self.loaded_files = [*self.loaded_files, {"name": file_data.name, "path": file_data.path}]
        self.list_view.append(ListItem(Label(file_data["name"])))
        self.loaded_files.append({"name": file_data["name"], "path": file_data["path"]})
        # checking to make sure that the content is actually in there
        if file_data["content"] == "":
            try:
                with open(file_data["path"]) as f:
                    file_data["content"] = f.read()
                    f.close()
            except FileNotFoundError:
                pass
        self.architect_model.architect_state["code_files"] = self.architect_model.architect_state["code_files"] + [CodeFile(name=file_data["name"], path=file_data["path"], content=file_data["content"])]


    def remove_file_from_loaded_files(self, file_data):
        index = self.loaded_files.index({"name": file_data["name"], "path": file_data["path"]})
        self.list_view.pop(index)

        architect_code_files = self.architect_model.architect_state["code_files"]
        i = 0
        while i < len(architect_code_files):
            if architect_code_files[i]["path"] == file_data["path"]:
                architect_code_files.pop(i)
            else:
                i += 1
        self.architect_model.architect_state["code_files"] = architect_code_files

    @on(ChatInputArea.Submit)
    async def chat(self, event: ChatInputArea.Submit):
        #solution = self.architect_model.graph.invoke({"messages": [("user", event.input_area.text)], "iterations": 0, "error": ""})
        #self.architect_model.deepseek.invoke(code_gen_prompt.format(context=self.architect_model.format_code_files_for_llm(), messages=[("user", event.input_area.text)]))
        response = ""
        formatted_prompt = code_gen_prompt.format(context=self.architect_model.format_code_files_for_llm(), messages=[("user", event.input_area.text)])
        stream = self.architect_model.deepseek.astream(formatted_prompt)
        async for chunk in stream:
            self.output.text = self.output.text + str(chunk.content)
        assistant_messages = self.query_one("#assistant-messages")
        #original_contents = self.architect_model.find_code_file_by_path(generated_text.file_path)
        #assistant_messages.mount(ApplyChangesWidget(
            #original=original_contents if original_contents else "",
            #modified=generated_text.code,
            #file_name=generated_text.file_path.split("/")[-1]))
