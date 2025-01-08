import os
import re
from pathlib import Path
from typing import List, Set, Dict, Optional


class ContextCollector:
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.file_cache: Dict[str, str] = {}  # Cache file contents
        self.supported_extensions = ['py', 'js', 'jsx', 'ts', 'tsx', 'java', 'cpp', 'h', 'rs', 'go']

    def collect_context(self, query: str, starting_file: Optional[str] = None) -> List[str]:
        """
        Collect relevant files based on:
        1. Direct file mentions in query
        2. Keywords/topics from query
        3. If starting_file provided, related files to it
        4. Project structure proximity
        """
        relevant_files = set()

        # Strategy 1: Direct file mentions
        mentioned_files = self._find_file_mentions(query)
        relevant_files.update(mentioned_files)

        # Strategy 2: Keyword-based search
        keyword_files = self._find_files_by_keywords(query)
        relevant_files.update(keyword_files)

        # Strategy 3: Starting file context
        if starting_file:
            related_files = self._find_related_files(starting_file)
            relevant_files.update(related_files)

        # Strategy 4: Project structure proximity
        proximity_files = self._find_proximity_files(relevant_files)
        relevant_files.update(proximity_files)

        return list(relevant_files)

    def _find_file_mentions(self, text: str) -> Set[str]:
        """Find directly mentioned files in text"""
        files = set()
        # Regex pattern to match filenames with supported extensions
        file_pattern = re.compile(r'\b[\w\-./\\]+\.(?:' + '|'.join(self.supported_extensions) + r')\b')
        matches = file_pattern.findall(text)
        for match in matches:
            file_path = self.project_root / Path(match)
            if file_path.exists():
                files.add(str(file_path.resolve()))
        return files

    def _find_files_by_keywords(self, query: str) -> Set[str]:
        """Find files that contain keywords from the query"""
        keywords = self._extract_keywords(query)
        if not keywords:
            return set()

        matching_files = set()
        for file_path in self._iter_project_files():
            content = self._read_file(file_path)
            if content:
                if any(keyword.lower() in content.lower() for keyword in keywords):
                    matching_files.add(str(file_path.resolve()))
        return matching_files

    def _extract_keywords(self, text: str) -> Set[str]:
        """Extract keywords from the query by splitting on non-word characters"""
        # Simple keyword extraction; can be enhanced with NLP techniques
        keywords = set(re.findall(r'\b\w+\b', text))
        return keywords

    def _find_related_files(self, starting_file: str) -> Set[str]:
        """Find related files based on the starting file's directory"""
        related = set()
        start_path = self.project_root / Path(starting_file)
        if not start_path.exists():
            print(f"Starting file {start_path} does not exist.")
            return related

        if start_path.is_file():
            dir_path = start_path.parent
        else:
            dir_path = start_path

        # Include all supported files in the same directory
        for ext in self.supported_extensions:
            for file in dir_path.glob(f'*.{ext}'):
                related.add(str(file.resolve()))
        return related

    def _find_proximity_files(self, current_files: Set[str]) -> Set[str]:
        """
        Find files that are in the same or adjacent directories
        as the current relevant files.
        """
        proximity = set()
        for file in current_files:
            file_path = Path(file)
            parent_dir = file_path.parent
            # Include files from the parent directory
            for ext in self.supported_extensions:
                for f in parent_dir.glob(f'*.{ext}'):
                    proximity.add(str(f.resolve()))
            # Optionally, include files from child directories
            for ext in self.supported_extensions:
                for f in file_path.rglob(f'*.{ext}'):
                    proximity.add(str(f.resolve()))
        return proximity

    def _iter_project_files(self) -> List[Path]:
        """Iterate through all supported files in the project"""
        files = []
        for ext in self.supported_extensions:
            files.extend(self.project_root.rglob(f'*.{ext}'))
        return files

    def _read_file(self, file_path: Path) -> str:
        """Read and cache the content of a file"""
        path_str = str(file_path.resolve())
        if path_str in self.file_cache:
            return self.file_cache[path_str]
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self.file_cache[path_str] = content
            return content
        except (UnicodeDecodeError, FileNotFoundError, PermissionError) as e:
            print(f"Failed to read {file_path}: {e}")
            return ""
