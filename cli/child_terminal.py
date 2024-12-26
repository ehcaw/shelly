from process_monitor import ProcessMonitor
from typing import Optional
import zmq
import platform
import base64
import zlib
import subprocess
import traceback
import time
import os

class ChildTerminal:
    monitor: Optional[ProcessMonitor]
    def __init__(self, port=5555, terminal_app=None, session_name='zapper_session'):
        self.context = zmq.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.bind(f"tcp://*:{port}")
        self.system = platform.system()
        self.session_name = session_name
        self.terminal_process = None
        self.monitor = None
        self.tmux_stack = [""]
        self.last_stdout = ""
        self.last_stderr = ""
        self.error_log_file = f"/tmp/{session_name}_stderr.log"

    def send_code_segment(self, code_data):
        """
        Send code segments with metadata
        code_data = {
            'file_path': 'path/to/file',
            'code': 'actual code content',
            'metadata': {...},
            'action': 'analyze/edit/debug'
        }
        """
        # Compress the code content
        compressed_code = base64.b64encode(
            zlib.compress(code_data['code'].encode())
        ).decode()
        code_data['code'] = compressed_code

        # Send the data
        self.publisher.send_json(code_data)

    def open_new_terminal(self):
        """Create an interactive terminal session with proper error handling"""
        try:
            self.kill_tmux_session()

            subprocess.run(['tmux', 'new-session', '-d', '-s', self.session_name])
            subprocess.run(['tmux', 'pipe-pane', '-t', self.session_name,f'2> {self.error_log_file}'])

            # Open a new terminal window and attach to the tmux session
            if platform.system() == "Darwin":  # macOS
                apple_script = f'''
                    tell application "Terminal"
                        do script "tmux attach-session -t {self.session_name}"
                    end tell
                '''
                subprocess.Popen(['osascript', '-e', apple_script])
            elif platform.system() == "Linux":
                subprocess.Popen([
                    'gnome-terminal', '--', 'tmux', 'attach-session', '-t', self.session_name
                ])
            else:
                raise NotImplementedError("Windows not yet supported")

            # Allow some time for tmux session to start
            time.sleep(1)

            return True
        except Exception as e:
            print(f"Error creating tmux session: {e}")
            traceback.print_exc()
            return False

    def kill_tmux_session(self):
        """Kill the tmux session if it exists"""
        try:
            # Check if session exists
            result = subprocess.run(
                ['tmux', 'has-session', '-t', self.session_name],
                capture_output=True
            )
            if result.returncode == 0:  # Session exists
                subprocess.run(['tmux', 'kill-session', '-t', self.session_name])
        except Exception as e:
            print(f"Error killing tmux session: {e}")

    def read_tmux_output(self):
        """Read output from the tmux session"""
        try:
            # Capture the entire pane content with history
            result = subprocess.run(
                ['tmux', 'capture-pane', '-S -100', '-t', self.session_name, '-p'],  # Get more history
                capture_output=True,
                text=True
            )

            current_output = self.clean_tmux_output(result.stdout)
            lines = current_output.split('\n')

            error_lines = []
            in_error = False
            buffer_lines = []  # Keep recent lines in buffer

            for line in lines:
                # Keep a buffer of recent lines
                buffer_lines.append(line)
                if len(buffer_lines) > 5:  # Keep last 5 lines
                    buffer_lines.pop(0)

                if 'Traceback' in line or any(err in line for err in [
                    'SyntaxError:', 'NameError:', 'TypeError:', 'ValueError:',
                    'ImportError:', 'AttributeError:', 'RuntimeError:',
                    'IndentationError:', 'TabError:'
                ]):
                    in_error = True
                    # Add the buffer lines for context
                    error_lines.extend(buffer_lines)
                    continue

                if in_error:
                    error_lines.append(line)
                    # Look for patterns that indicate end of error
                    if not line.strip() or line.startswith(('$ ', '> ', 'zap>')):
                        in_error = False

            error_text = '\n'.join(line for line in error_lines if line.strip())

            if error_text and error_text != self.last_stderr:
                self.last_stderr = error_text
                return {
                    'stdout': "",
                    'stderr': error_text
                }

            return None

        except Exception as e:
            print(f"Error reading tmux session: {e}")
            traceback.print_exc()
            return None

    def clean_tmux_output(self, raw_output: str) -> str:
        """Clean and format tmux output by removing ANSI escape sequences and extra whitespace"""
        import re

        # Remove ANSI escape sequences
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        # Remove unicode characters commonly used in prompts
        unicode_chars = re.compile(r'[\ue0b0-\ue0b3\ue5ff\ue615\ue606\uf48a\uf489\ue0a0]')

        # Clean the output
        cleaned = ansi_escape.sub('', raw_output)
        cleaned = unicode_chars.sub('', cleaned)

        # Preserve indentation but remove other whitespace
        lines = []
        for line in cleaned.split('\n'):
            indent = len(line) - len(line.lstrip())
            cleaned_line = line.strip()
            if cleaned_line:
                lines.append(' ' * indent + cleaned_line)

        return '\n'.join(lines)
    def is_terminal_active(self) -> bool:
        """Check if terminal session is active and valid"""
        return (self.terminal_process is not None and
                self.terminal_process.poll() is None)
    def send_to_terminal(self, command: str) -> Optional[str]:
        """Send a command to the tmux session"""
        try:
            subprocess.run(['tmux', 'send-keys', '-t', self.session_name, command, 'C-m'])
            return "Command sent"
        except Exception as e:
            print(f"Error sending to tmux session: {e}")
            return None
