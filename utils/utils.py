# [START utils.py]
"""
This file creates a dependency graph that depicts the relationships between files. It will read the error stack, and attempt to parse it. Then, using the files mentioned, add everything.
If the user does not provide a flag, the graph will only create itself from the error stack.
If the user does provide "-g", the graph will contain all files from the repo, with respect to the .gitignore.
If the user does provide "-r", the graph will contain all files from the error stack, alongside all files that are imported/included in the source file, and recursively call itself until all relationships are exhausted.

@usage: "splat <?-g> <?-r> <?entrypoint>"
@note: if "splat" is not called with an entrypoint, the user will provide their own entrypoint when prompted
@note: entrypoint will **always** be provided; assume there are 3 possibilities only
"""
import os
from typing import List, Set, Dict, Optional
import ast
import re
import subprocess
import signal
from pathlib import Path
from repomixer.context_collector import ContextCollector
from langchain.schema import BaseMessage

# Example run
def main(error_info: str, flag: Optional[str] = None, project_root: str = './'):
  project_root = os.getcwd()
  error_files = [os.path.join(project_root, file) for file in parse_error_stack(error_info)]
  print("************ERROR FILES*************")
  print(error_files)
  print("************ERROR FILES*************")

  if isinstance(flag, str):
    print("FLAG CALL: " + flag)

  if flag == '-r':
    graph = build_adjacency_list(error_files, project_root)
    all_related_files = get_nth_related_files(error_files, graph)
    return run_mock_repopack(list(all_related_files))
  return run_mock_repopack(error_files)

def is_project_file(file_path: str, project_root: str) -> bool:
  return os.path.commonpath([file_path, project_root]) == project_root

'''
This function parses through a typical Python error trace stack and returns a list of all unique file paths found in the trace.
@param error_info: str - a string that will be parsed for errors
@note: The function uses a regular expression to extract file paths from the error message.
@note: If a file path doesn't exist on the filesystem, it will not be included in the returned list.
'''
def parse_error_stack(error_info: str) -> List[str]:
  """
  Parse the error stack trace and return a list of all unique file paths involved.

  Args:
  error_info (str): The full error stack trace as a string.

  Returns:
  List[str]: A list of unique file paths involved in the error(s).
  """
  files = []
  # This regex looks for file paths in various formats, including the command output
  file_pattern = re.compile(r'(?:File "([^"]+)"|\b(\S+\.py)\b)')

  # Process each line of the error_info
  for line in error_info.split('\n'):
    matches = file_pattern.findall(line)
    for match in matches:
      # The regex returns a tuple for each match, we take the non-empty string
      file_path = next((m for m in match if m), None)
      if file_path:
        file_path = file_path.strip()
        # Remove any quotes around the file path
        file_path = file_path.strip("'\"")
        if os.path.exists(file_path):
          files.append(file_path)

  return list(dict.fromkeys(files))

'''
This function calls repopack to be used with a required parameter.
@param paths: List[str] - A list of file paths to analyze using repopack.
@returns: Dict - The JSON output from repopack parsed into a Python dictionary.
'''
def run_mock_repopack(paths: List[str], style: str = 'json') -> str:
  """
  A mock function that simulates what repopack might do.
  It returns a string with file paths and their full content.

  Args:
  paths (List[str]): List of file paths to be processed.
  style (str): Output style (default is 'json', but not used in this mock version).

  Returns:
  str: A string representation of the full file contents.
  """
  result = []
  for path in paths:
    if os.path.exists(path):  # Some paths are hallucinative / not real
      with open(path, 'r') as f:
        content = f.read()
      result.append(f"File: {path}\nContent:\n{content}\n")

  return "\n" + "="*50 + "\n".join(result) + "="*50 + "\n"

'''
This function runs through a source file and grabs all files linked by any Nth degree connection.
@param start_files: List[str] - The files to start with for finding related files.
@param graph: Dict[str, List[str]] - The adjacency list representing the relationships between files.
@returns: Set[str] - A set of all files related to the start_files to any Nth degree.
'''
def get_nth_related_files(start_files: List[str], graph: Dict[str, List[str]]) -> Set[str]:
  related_files = set(start_files)
  planned_visit = list(start_files)
  possible_files = set()

  while planned_visit:
    current = planned_visit.pop(0)
    possible_files.add(current)

    for neighbor in graph.get(current, []):
      if neighbor not in related_files:
        related_files.add(neighbor)
        planned_visit.append(neighbor)

  return possible_files

'''
Builds an adjacency list from a list of files.
@param files: List[str] - The list of Python files to analyze for import relationships.
@param project_root: str - The root directory of the project to ensure valid paths.
@returns: Dict[str, List[str]] - An adjacency list where each key is a file and its value is a list of imported files.
'''
def build_adjacency_list(files: List[str], project_root: str) -> Dict[str, List[str]]:
    adjacency_list = {}
    processed_files = set()

    def process_file(file: str):
        if file in processed_files or not is_project_file(file, project_root):
            return

        processed_files.add(file)
        imports = set()
        tree = None

        try:
            with open(file, 'r') as f:
                content = f.read()
                try:
                    tree = ast.parse(content)
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            imports.update(alias.name for alias in node.names)
                        elif isinstance(node, ast.ImportFrom) and node.module:
                            imports.add(node.module)
                except SyntaxError:
                    pass
        except FileNotFoundError:
            return
        except Exception as e:
            return

        adjacency_list[file] = []
        file_dir = os.path.dirname(file)

        for imp in imports:
            module_paths = []
            if '.' in imp:
                module_paths.append(os.path.join(project_root, *imp.split('.')) + '.py')
            else:
                module_paths.extend([
                    os.path.join(file_dir, f"{imp}.py"),
                    os.path.join(project_root, f"{imp}.py")
                ])

            for module_path in module_paths:
                if os.path.exists(module_path):
                    adjacency_list[file].append(module_path)
                    # Recursively process the imported file
                    process_file(module_path)
                    break
            else:
              pass
                #print(f"Warning: Imported module {imp} does not exist in the same directory or project root.")

        if tree is None and imports:
            adjacency_list[file].append(f"{file} (unresolved imports due to syntax errors)")

    # Start processing with the initial list of files
    for file in files:
        process_file(file)

    return adjacency_list



################################################## NOT IMPLEMENTED BELOW #####################################################################
'''
This function uses a command and tries to check what type the file/directory is.
The idea is that we will have robust solutions specifically for different project types,
meaning that we need to determine what kind of project/file the user is working with.
'''
def detect_framework_or_language(command, directory='.'):
  # Dictionary to map commands, file presence, or file extensions to frameworks/languages
  indicators = {
    'go': {
      'commands': ['go run'],
      'files': ['go.mod'],
      'extensions': ['.go']
    },
    'rust': {
      'commands': ['cargo run'],
      'files': ['Cargo.toml'],
      'extensions': ['.rs']
    },
    'kotlin': {
      'commands': ['kotlinc', 'kotlin'],
      'files': [],
      'extensions': ['.kt']
    },
    'scala': {
      'commands': ['scala', 'sbt run'],
      'files': ['build.sbt'],
      'extensions': ['.scala']
    },
    'swift': {
      'commands': ['swift', 'swiftc'],
      'files': ['Package.swift'],
      'extensions': ['.swift']
    },
    'r': {
      'commands': ['Rscript'],
      'files': [],
      'extensions': ['.r', '.R']
    },
    'perl': {
      'commands': ['perl'],
      'files': [],
      'extensions': ['.pl', '.pm']
    },
    'haskell': {
      'commands': ['ghc', 'runghc'],
      'files': [],
      'extensions': ['.hs']
    },
    'lua': {
      'commands': ['lua'],
      'files': [],
      'extensions': ['.lua']
    },
    'julia': {
      'commands': ['julia'],
      'files': [],
      'extensions': ['.jl']
    },
    'c': {
      'commands': ['gcc'],
      'files': [],
      'extensions': ['.c', '.cpp']
    },
    'java': {
      'commands': ['javac', 'java'],
      'files': [],
      'extensions': ['.java']
    },
    'javascript': {
      'commands': ['node'],
      'files': [],
      'extensions': ['.js', '.jsx']
    },
    'typescript': {
      'commands': ['node'],
      'files': [],
      'extensions': ['.ts', '.tsx']
    },
    'python': {
      'commands': ['python', 'python3'],
      'files': [],
      'extensions': ['.py']
    },
    'nextjs': {
      'commands': ['next', 'npm run dev', 'yarn dev'],
      'files': ['next.config.js', 'pages'],
      'extensions': ['.jsx', '.tsx']
    },
    'fastapi': {
      'commands': ['uvicorn', 'python main.py'],
      'files': ['main.py'],
      'extensions': ['.py']
    },
    'react': {
      'commands': ['react-scripts start', 'npm start', 'yarn start'],
      'files': ['src/App.js', 'public/index.html'],
      'extensions': ['.jsx', '.tsx', '.js', '.ts']
    },
    'django': {
      'commands': ['python manage.py runserver', 'django-admin'],
      'files': ['manage.py', 'settings.py'],
      'extensions': ['.py']
    },
    'flask': {
      'commands': ['flask run', 'python app.py'],
      'files': ['app.py', 'wsgi.py'],
      'extensions': ['.py']
    },
    'vue': {
      'commands': ['vue-cli-service serve', 'npm run serve'],
      'files': ['src/main.js', 'public/index.html'],
      'extensions': ['.vue']
    },
    'angular': {
      'commands': ['ng serve', 'npm start'],
      'files': ['angular.json', 'src/main.ts'],
      'extensions': ['.ts']
    },
    'express': {
      'commands': ['node server.js', 'npm start'],
      'files': ['server.js', 'app.js'],
      'extensions': ['.js']
    },
    'spring-boot': {
      'commands': ['./mvnw spring-boot:run', 'java -jar'],
      'files': ['pom.xml', 'src/main/java'],
      'extensions': ['.java']
    },
    'ruby-on-rails': {
      'commands': ['rails server', 'rails s'],
      'files': ['config/routes.rb', 'app/controllers'],
      'extensions': ['.rb']
    },
    'laravel': {
      'commands': ['php artisan serve'],
      'files': ['artisan', 'app/Http/Kernel.php'],
      'extensions': ['.php']
    },
    'dotnet': {
      'commands': ['dotnet run', 'dotnet watch run'],
      'files': ['Program.cs', '.csproj'],
      'extensions': ['.cs']
    },
  }

def find_files_in_directory(directory: str, file_paths: List[str]) -> Dict[str, str]:
    """
    Find files in a directory given their full or partial paths.

    Args:
        directory (str): Root directory to search in.
        file_paths (list): List of file paths or names to find.

    Returns:
        dict: Dictionary mapping searched paths to found absolute paths.
    """
    root = Path(directory).resolve()
    found_files = {}

    for file_path in file_paths:
        # Convert to Path object
        search_path = Path(file_path)

        # Strategy 1: If it's just a filename
        if len(search_path.parts) == 1:
            matches = list(root.rglob(search_path.name))
            if matches:
                found_files[file_path] = str(matches[0].resolve())
            continue  # Move to the next file_path

        # Strategy 2: If it's a partial path
        # Ensure the pattern is relative by removing any leading slashes
        pattern = search_path.as_posix().lstrip('/\\')

        # rglob expects a relative pattern, so ensure it's relative
        if pattern:
            matches = list(root.rglob(pattern))
            if matches:
                found_files[file_path] = str(matches[0].resolve())
                continue  # Move to the next file_path

        # Strategy 3: Try to match just the filename with directory pattern
        filename = search_path.name
        parent_dir = search_path.parent

        # Iterate through all matches of the filename
        for possible_match in root.rglob(filename):
            try:
                # Get the relative path from root
                relative_match = possible_match.relative_to(root)
                # Check if the parent_dir is a suffix of the relative path
                if Path(parent_dir).as_posix() in relative_match.as_posix():
                    found_files[file_path] = str(possible_match.resolve())
                    break  # Stop after finding the first relevant match
            except ValueError:
                # possible_match is not under root
                continue

    return found_files
'''
def calculate_semantic_similarity(word1, word2):
    # Get synsets for both words
    synsets1 = wordnet.synsets(word1)
    synsets2 = wordnet.synsets(word2)

    if not synsets1 or not synsets2:
        return 0.0

    # Calculate maximum similarity between any pair of synsets
    max_sim = 0.0
    for syn1 in synsets1:
        for syn2 in synsets2:
            sim = 0
            if syn1:
                sim = syn1.path_similarity(syn2)
            if sim and sim > max_sim:
                max_sim = sim
    return max_sim
    '''

def error_repomix(entry_file: str, flag: str, query: Optional[str]):
    entry_file_path = find_files_in_directory(os.getcwd(), [entry_file])
    cmd = ['repomix', '--output-show-line-numbers', '-o shellypack.txt']
    match flag:
        case "-r":
            context_collector = ContextCollector("")
            related_files = context_collector.collect_context(query if query else "", entry_file_path)
            cmd.append(related_files[:])
        case "-g":
            cmd = cmd # repopack everything
        case _:
            cmd.append(entry_file_path[entry_file])
    if os.path.exists('shellypack.txt'):
        os.remove('shellypack.txt') # delete the repopack if it exists
    subprocess.run(['repomix', '--output-show-line-numbers', '-o shellypack.txt']) # should add all related files to the array
    try:
        with open("shellypack.txt", 'r') as f:
            print(f.read())
        #os.remove("shellypack.txt")
    except FileNotFoundError as e:
        print(f'Repomix was unsuccessful...{e}')


################################################## NOT IMPLEMENTED ABOVE #####################################################################
def extract_filename_with_extension(command):
  # Regular expression to match file names with extensions for the supported languages
  match = re.search(r'(\b\w+\.(go|rs|kt|scala|swift|r|pl|lua|jl|c|java|ts|py)\b)', command, re.IGNORECASE)
  if match:
    # Return the full file name with its extension
    return match.group(1)
  return None


def kill_process_on_port(port):
    try:
        # Find the PID of the process using the specified port
        result = subprocess.run(["lsof", "-t", f"-i:{port}"], capture_output=True, text=True)
        pid = result.stdout.strip()

        if pid:
            # Kill the process with the found PID
            os.kill(int(pid), signal.SIGKILL)
        else:
          return
    except Exception as e:
        print(f"Error: {e}")

# [END utils.py]

def new_message_of_type(message_type: type[BaseMessage], *, content: str = "", **kwargs):
    """
    Creates a new message of the specified type with content and additional kwargs.
    message_type should be AIMessage, HumanMessage, etc. - not BaseMessage itself
    """
    if not issubclass(message_type, BaseMessage):
        raise ValueError("message_type must be a subclass of BaseMessage")

    return message_type(
        content=content,
        additional_kwargs={
            **kwargs,
        },
    )
