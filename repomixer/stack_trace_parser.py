import os
import re
from typing import List, Set, Optional

class StackTraceParser:
    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.getcwd()
        self.file_pattern = re.compile(r'(?:'
                    r'File "([^"]+)"|'  # Python
                    r'at\s+(?:.*?\()?([^\s:()]+?\.[a-zA-Z]+)(?::\d+)?(?:\))?|'  # JS/Java
                    r'\b(/[^:]+\.[a-zA-Z]+)|'  # Absolute paths
                    r'\b(\S+\.[a-zA-Z]+)\b'  # Any file with extension
                    r')'
            )
        # Common system paths to exclude
        self.exclude_patterns = [
            r'node_modules',
            r'site-packages',
            r'internal/modules',
            r'lib/python[\d.]+',
            r'java/lang',
        ]
    def normalize_path(self, path: str) -> str:
            """Convert relative paths to absolute and normalize slashes"""
            if not os.path.isabs(path):
                path = os.path.join(self.project_root, path)
            return os.path.normpath(path)

    def should_include_file(self, file_path: str) -> bool:
        """Check if file should be included in results"""
        # Exclude system files
        for pattern in self.exclude_patterns:
            if re.search(pattern, file_path):
                return False

        # Check if file exists
        normalized_path = self.normalize_path(file_path)
        return os.path.exists(normalized_path)

    def extract_files(self, error_trace: str) -> List[str]:
        """Extract file paths from error trace"""
        files: Set[str] = set()

        matches = self.file_pattern.finditer(error_trace)
        for match in matches:
            # Get the first non-None group
            file_path = next((
                group for group in match.groups()
                if group is not None
            ), None)

            if file_path and self.should_include_file(file_path):
                normalized_path = self.normalize_path(file_path)
                files.add(normalized_path)

        return list(files)

    def get_related_files(self, files: List[str]) -> List[str]:
        """Get related files from the same directories"""
        related: Set[str] = set()

        for file_path in files:
            dir_path = os.path.dirname(file_path)
            if os.path.exists(dir_path):
                for f in os.listdir(dir_path):
                    if f.endswith(('.py', '.js', '.java', '.ts', '.rs','.kt','.scala','.swift','.r','.R', '.pl', '.pm', '.hs', '.lua', '.c', '.cpp', '.jsx', '.tsx', )):  # add more extensions as needed
                        full_path = os.path.join(dir_path, f)
                        related.add(full_path)

        return list(related)
