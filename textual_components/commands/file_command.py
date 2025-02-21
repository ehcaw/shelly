from .registry import SlashCommand, SlashCommandResult
from typing import List, Optional
from pathlib import Path
import fnmatch
import os
from functools import lru_cache

class FileCommand(SlashCommand):
    def __init__(self):
        super().__init__()
        self.name = "file"
        self.description = "Search for files"
        self.icon = "📄"
        self.cwd = os.getcwd()

    async def complete(self, args: List[str]) -> List[str]:
        # Reuse your existing file search logic
        files = self.get_all_files_in_cwd()
        if not args:
            return files[:10]

        search_term = args[-1].lower()
        return [
            f for f in files
            if all(term in f.lower() for term in search_term.split())
        ][:10]

    async def execute(self, args: List[str]) -> SlashCommandResult:
        if not args:
            return SlashCommandResult("Please specify a file")
        return SlashCommandResult(args[0])

    @lru_cache
    def get_all_files_in_cwd(self, directory: Optional[str] = None, max_files=100) -> List[str]:
        cwd = directory if directory else self.cwd
        files = []
        # Extensive list of directories to ignore
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

        # Extensive list of file patterns to ignore
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

        for root, dirs, filenames in os.walk(cwd, topdown=True):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in ignore_dirs]

            for filename in filenames:
                # Skip files matching ignore patterns
                if any(fnmatch.fnmatch(filename, pattern) for pattern in ignore_files):
                    continue

                # Get relative path
                rel_path = os.path.relpath(os.path.join(root, filename), cwd)

                # Skip paths that contain any of the ignored directory names
                # (handles nested cases like 'something/node_modules/something')
                if any(ignored_dir in rel_path.split(os.sep) for ignored_dir in ignore_dirs):
                    continue

                files.append(rel_path)

                if len(files) >= max_files:
                    return files

        return sorted(str(file) for file in files)  # Sort for consistent ordering
