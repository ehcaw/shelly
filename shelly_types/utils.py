from pathlib import Path
import os
from typing import Optional, List

def llm_response_helper(response) -> str:
    """Convert the llm response to string content"""
    try:
        if isinstance(response, list):
            response_content = response[0].content if response else ""
        elif hasattr(response, "content"):
            response_content = response.content
        else:
            response_content = str(response)
        return response_content
    except Exception as e:
        return "There was an issue processing the llm response"

def find_file(filename: str, search_dir: Path = None, ignore_dirs: set = None) -> Optional[Path]:
    """
    Search for a file recursively starting from search_dir.
    Returns the relative path to the file if found, None otherwise.
    """
    # Default to current working directory if no search_dir provided
    search_dir = search_dir or Path.cwd()

    # Default ignore directories
    if ignore_dirs is None:
        ignore_dirs = {
            '.git', '__pycache__', 'node_modules', 'venv', '.venv',
            'env', '.env', 'build', 'dist', '.idea', '.vscode'
        }

    try:
        # Convert search_dir to absolute path
        search_dir = search_dir.resolve()

        # Walk through directory tree
        for root_dir, dirs, files in os.walk(search_dir):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            # Check if file exists in current directory
            if filename in files:
                # Get absolute path of the file
                file_path = Path(root_dir) / filename
                # Convert to relative path from current working directory
                return file_path.relative_to(Path.cwd())

        return None

    except Exception as e:
        print(f"Error searching for file: {e}")
        return None
