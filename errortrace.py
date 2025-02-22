import subprocess
import os
import sys
import shlex
import threading
import json
import logging

logging.basicConfig(level=logging.ERROR)

def run_command(command):
    process = subprocess.Popen(
        shlex.split(command),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        universal_newlines=True
    )

    def read_output(pipe, lines):
        for line in pipe:
            line = line.strip()
            lines.append(line)

    stdout, stderr = [], []

    stdout_thread = threading.Thread(target=read_output, args=(process.stdout, stdout))
    stderr_thread = threading.Thread(target=read_output, args=(process.stderr, stderr))

    stdout_thread.start()
    stderr_thread.start()

    stdout_thread.join()
    stderr_thread.join()

    return_code = process.wait()

    return '\n'.join(stdout), '\n'.join(stderr), return_code

def splat_find(command ):
    if command:
        print(f"Last command was: {command}")
        # Add specific logic to process this command
        stdout, stderr, returncode = run_command(command)
        json_file = {"stdout": stdout, "stderr": stderr, "returncode": returncode}
        return json.dumps(json_file)
    else:
        print("No last command found.")
        return None
