# auto_debugger.py
import time
import zmq
import threading
import sys
import traceback

#from relational import relational_error_parsing_function

class Listener:
    def __init__(self, port=5555, max_stack_size=500):
        self.context = zmq.Context()
        self.running = False
        self.subscriber_thread = None
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.connect(f"tcp://127.0.0.1:{port}")
        self.subscriber.setsockopt_string(zmq.SUBSCRIBE, "")
        self.max_stack_size = max_stack_size
        self.stdout_stack = [""]
        self.stderr_stack = [""]

    def start(self):
        """Start the publisher thread"""
        self.running = True
        self.subscriber_thread = threading.Thread(target=self.run_subscriber)
        self.subscriber_thread.daemon = True
        self.subscriber_thread.start()
        print("ZMQ publisher thread started")

    def manage_stack(self, stack, new_item):
        """Manage stack size and add new item"""
        if len(stack) >= self.max_stack_size:
            stack.pop(0)  # Remove oldest item
        stack.append(new_item)

    def run_subscriber(self):
        while self.running:
            try:
                message = self.subscriber.recv_json(flags=zmq.NOBLOCK)
                if isinstance(message, dict) and message.get('type') == 'tmux_output':
                    tmux_pane_output = message.get('data')
                    if tmux_pane_output and tmux_pane_output.get('stderr'):
                        current_stderr = tmux_pane_output['stderr']

                        # Only process if we have new stderr content
                        if current_stderr and current_stderr != self.stderr_stack[-1]:
                            # Print full error stack with formatting
                            print("\n" + "="*50)
                            print("Error Detected:")
                            print("="*50)
                            print(current_stderr)
                            print("="*50)
                            print("\nzap> ", end='', flush=True)

                            # Update the stack
                            self.manage_stack(self.stderr_stack, current_stderr)

            except zmq.Again:
                time.sleep(0.1)
            except Exception as e:
                print(f"Error in subscriber: {e}")
                traceback.print_exc()
                time.sleep(0.1)

    def stop(self):
        """Stop publisher threads"""
        self.running = False
        if self.subscriber_thread:
            self.subscriber_thread.join()
        self.context.term()



#if __name__ == "__main__":
