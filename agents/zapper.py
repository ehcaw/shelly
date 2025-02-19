from typing import TypedDict, List, Dict
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from langchain.prompts import ChatPromptTemplate


class SimpleState(TypedDict):
    messages: List[Dict[str, str]]  # Store conversation history
    summaries: List[BaseMessage]
    current_input: str              # Current user input
    action_output: str             # Current response
    should_end: bool


class Zapper:
    def __init__(self, summarizer):
        self.state = SimpleState(
            messages=[],
            summaries=[],
            current_input="",
            action_output="",
            should_end=False
        )
        self.summarizer_llm = summarizer
        self.system_prompt = ChatPromptTemplate.from_messages([
            ("system", "You are a helpful assistant that summarizes messages to manage context. Summarize the given input, extracting useful information from the response for future interaction"),
            ("user", "{input}"),
        ])

    def add_user_input_to_summaries(self, input):
        self.state["summaries"].append(HumanMessage(content=input))

    def summarize_message(self, response):
        prompt = self.system_prompt.format_messages(input=response)
        summarized_response = self.summarizer_llm.invoke(prompt)

        # If summarized_response is a string
        if isinstance(summarized_response, str):
            self.state["summaries"].append(AIMessage(content=summarized_response))
        else:
            # If it's already an AIMessage
            self.state["summaries"].append(summarized_response)
