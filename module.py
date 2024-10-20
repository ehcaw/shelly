"""
"""
# [START module.py]
import os
from typing import List
from te import relational_error_parsing_function


def main():
  """
  Running "splat <?-r> '<python3 filename.py>' will compile the Python file in a contained environment.

  If splat is called with no flag, then the error traces will only be scanned.
  If splat is called with a -r flag, then the error traces and its Nth degree connections will be scanned.

  If splat is not called with an entrypoint <python3 ?.py> then splat will prompt the user for an entrypoint.
  """

  '''CLI NEEDS TO PROMPT USER HERE + CLI NEEDS TO RETURN BACK FLAG & ENTRYPOINT'''

  # Handle relational adjacency list, and feed this to LLM
  entrypoint: List[str] = [] # <-- FILL IT OUT HERE
  flag: str = ""
  repopack: str = relational_error_parsing_function(entrypoint, flag)

  # LLM now takes the data (all file context as type str, error message as type str)


# [END module.py]