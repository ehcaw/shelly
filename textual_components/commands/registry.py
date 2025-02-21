from typing import Dict, Type, List
from dataclasses import dataclass

@dataclass
class SlashCommandResult:
    content: str
    replace_full_line: bool = False

class SlashCommand:
    def __init__(self):
        self.name: str = ""
        self.description: str = ""
        self.icon: str = "🔍"

    async def complete(self, args: List[str]) -> List[str]:
        """Return completion suggestions"""
        return []

    async def execute(self, args: List[str]) -> SlashCommandResult:
        """Execute the command"""
        pass

class SlashCommandRegistry:
    def __init__(self):
        self._commands: Dict[str, SlashCommand] = {}

    def register(self, command: SlashCommand):
        self._commands[command.name] = command

    def get_command(self, name: str) -> SlashCommand | None:
        return self._commands.get(name)

    def get_all_commands(self) -> List[SlashCommand]:
        return list(self._commands.values())
