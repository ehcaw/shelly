
import threading
import time

class ProcessMonitor:
    def __init__(self, child_terminal):
        self.child_terminal = child_terminal
        self.monitor_thread = None
        self.poll_interval = 1
        self.is_running = False

    def start_monitoring(self):
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self.monitor_tmux)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        print('monitor thread starting')
    def monitor_tmux(self):
        while self.is_running:
            try:
                output = self.child_terminal.read_tmux_output()
                if output:  # Only send if there are changes
                    self.child_terminal.publisher.send_json({
                        'type': 'tmux_output',
                        'data': output,
                        'timestamp': time.time()
                    })
                time.sleep(self.poll_interval)
            except Exception as e:
                print(f"Error in monitor: {e}")
                time.sleep(self.poll_interval)
