from agents.final_graph import Splatter
from pathlib import Path
import asyncio

async def test_documentation_loading():
    print("\n=== Testing Documentation Loading ===")
    splatter = await Splatter.create_and_initialize()

    # Test loading FastAPI documentation
    print("Loading FastAPI documentation...")
    await splatter.load_documentation("https://fastapi.tiangolo.com/")

    # Test searching loaded documentation
    print("\nSearching documentation for 'path parameters'...")
    results = await splatter.search_documentation("path parameters")
    for result in results[:2]:  # Show first 2 results
        print(f"Found in: {result['source']}")
        print(f"Preview: {result['content'][:200]}...")
        print(f"Relevance score: {result['relevance']}\n")

async def test_project_analysis():
    print("\n=== Testing Project Analysis ===")
    splatter = await Splatter.create_and_initialize()

    # Create a temporary test project
    test_project = Path("./test_project")
    test_project.mkdir(exist_ok=True)

    # Create some test files
    (test_project / "main.py").write_text("""
from fastapi import FastAPI
from .utils import helper_function

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
    """)

    (test_project / "utils.py").write_text("""
def helper_function():
    return "I'm helping!"
    """)

    # Load and analyze project
    print("Loading test project...")
    await splatter.load_project(str(test_project))

    # Get project structure
    print("\nProject structure:")
    structure = splatter.get_project_structure(str(test_project))
    print(f"Files: {structure['files']}")
    print(f"Dependencies: {structure['dependencies']}")
    print(f"Import graph: {structure['import_graph']}")

async def test_code_analysis():
    print("\n=== Testing Code Analysis ===")
    splatter = await Splatter.create_and_initialize()

    test_code = """
def calculate_total(items: list[dict]) -> float:
    return sum(item['price'] * item['quantity'] for item in items)

class ShoppingCart:
    def __init__(self):
        self.items = []

    def add_item(self, item: dict):
        self.items.append(item)

    def get_total(self) -> float:
        return calculate_total(self.items)
    """

    print("Analyzing code...")
    analysis = await splatter.analyze_code(test_code)
    print("\nAnalysis results:")
    print(f"Functions found: {analysis['functions']}")
    print(f"Classes found: {analysis['classes']}")
    print(f"Potential issues: {analysis['potential_issues']}")

async def test_conversation():
    print("\n=== Testing Conversation ===")
    splatter = await Splatter.create_and_initialize()

    # First load some context
    await splatter.load_documentation("https://fastapi.tiangolo.com/")

    # Test various types of queries
    queries = [
        "How do I create a FastAPI endpoint that accepts JSON data?",
        "Show me an example of path parameters in FastAPI",
        "What's the difference between query and path parameters?",
    ]

    for query in queries:
        print(f"\nQuery: {query}")
        responses = await splatter.process_message(query)
        for response in responses:
            print(f"Response: {response[:200]}...")  # Show first 200 chars

async def test_code_generation():
    print("\n=== Testing Code Generation ===")
    splatter = await Splatter.create_and_initialize()

    # Load FastAPI documentation for context
    await splatter.load_documentation("https://fastapi.tiangolo.com/")

    # Test code generation prompts
    prompts = [
        "Create a FastAPI endpoint that handles file uploads",
        "Generate a Pydantic model for a user with email and password",
        "Write a function that validates JWT tokens",
    ]

    for prompt in prompts:
        print(f"\nPrompt: {prompt}")
        responses = await splatter.process_message(prompt)
        for response in responses:
            print(f"Generated code:\n{response}")

async def cleanup_test_files():
    """Clean up any test files created during testing"""
    import shutil
    test_project = Path("./test_project")
    if test_project.exists():
        shutil.rmtree(test_project)

async def main():
    try:
        # Run all tests
        await test_documentation_loading()
        await test_project_analysis()
        await test_code_analysis()
        await test_conversation()
        await test_code_generation()

    except Exception as e:
        print(f"Error during testing: {e}")
        raise

    finally:
        # Clean up
        await cleanup_test_files()

if __name__ == "__main__":
    asyncio.run(main())
