from pathlib import Path
import pytest
from agents.react_graph import Splatter

def test_basic_operations():
    splatter = Splatter()

    # Test cases with initial states
    test_cases = [
        # Test file loading
        {
            "messages": [{
                "role": "user",
                "content": "Load and analyze the contents of test_file.py"
            }],
            "current_action_list": [],
            "should_end": False,
            "action_input": {
                "file_path": Path("test_file.py")
            }
        },

        # Test code analysis
        {
            "messages": [{
                "role": "user",
                "content": "Analyze this code: def hello(): print('world')"
            }],
            "current_action_list": [],
            "should_end": False,
            "action_input": {
                "code": "def hello(): print('world')",
                "analysis_type": "general"
            }
        },

        # Test code explanation
        {
            "messages": [{
                "role": "user",
                "content": "Explain this code in detail: for i in range(10): print(i)"
            }],
            "current_action_list": [],
            "should_end": False,
            "action_input": {
                "code": "for i in range(10): print(i)",
                "detail_level": "high"
            }
        }
    ]

    # Run each test case
    for test_case in test_cases:
        result = splatter.graph.invoke(test_case)
        print("\nTest Case Result:")
        print("Messages:", result["messages"])
        print("Action Output:", result.get("action_output"))
        print("Observation:", result.get("observation"))
        print("-" * 50)

if __name__ == "__main__":
    test_basic_operations()
