import click
import sys
import cmd
from process_monitor import ProcessMonitor
from listener import Listener
from child_terminal import ChildTerminal
from agents.zapper import Zapper
import subprocess
import shlex
import os
from langchain_core.messages import HumanMessage
import traceback

class ZapShell(cmd.Cmd):
    intro = 'Welcome to the Zap CLI. Type help or ? to list commands.\n'
    prompt = 'zap> '

    def __init__(self):
        super().__init__()
        self.ctx = None
        self.zapper = None
        self.child_terminal = None
        self.zapper = Zapper()

    # Command definitions
    def do_hello(self, arg):
        """Say hello"""
        click.echo('Hello!')

    def do_echo(self, arg):
        """Echo the input"""
        click.echo(arg)

    def do_exit(self, arg):
        """Exit the application"""
        click.echo('Goodbye!')
        if self.child_terminal:
            if self.child_terminal.monitor:
                self.child_terminal.monitor.is_running = False
            if self.child_terminal.terminal_process:
                self.child_terminal.terminal_process.terminate()
            self.child_terminal.kill_tmux_session()
        click.echo('Goodbye!')
        return True
        return True

    def do_start(self, arg):
        """Start up the terminal session using tmux"""
        self.listener = Listener()
        self.listener.start()
        #self.zapper.run_subscriber()
        self.child_terminal= ChildTerminal(session_name='zapper_session')
        if self.child_terminal.open_new_terminal():
            self.child_terminal.monitor = ProcessMonitor(self.child_terminal)
            self.child_terminal.monitor.start_monitoring()
        else:
            click.echo("Failed to start terminal session")

    def do_debug(self, entrypoint):
        try:
            if not entrypoint:
                raise Exception("No command provided")
            subprocess.run(entrypoint.split(), capture_output=True, check=True, text=True)
            print("No error with your program! :)")
        except subprocess.CalledProcessError as error:
            traceback: str = error.stderr if error.stderr else str(error)
            print(traceback)
        except Exception as e:
            print(e)

    def do_helper(self, arg):
        if self.zapper:
            try:
                initial_state = {
                    "messages": [HumanMessage(content="help")],
                    "next": "help_branch",
                }
                seen_messages = set()

                for event in self.zapper.graph.stream(initial_state):
                    for value in event.values():
                        if "messages" not in value:
                            continue

                        # Get only new messages
                        new_messages = [
                            msg for msg in value["messages"]
                            if msg.content not in seen_messages
                        ]

                        for message in new_messages:
                            if not hasattr(message, 'content'):
                                continue

                            # Add to seen messages
                            seen_messages.add(message.content)

                            # Print with appropriate prefix
                            if message.type == "assistant":
                                print(f"\nAssistant: {message.content}")
                            elif message.type == "human":
                                print(f"\nYou: {message.content}")

                            # If message contains file context, format it nicely
                            #if "file_context" in value:
                                #self.format_file_context(value["file_context"])
            except Exception as e:
                print(f"Error in helper: {e}")
                traceback.print_exc()
        else:
            print("The zapper hasn't been initialized :( please try again")
            return

    def do_run(self, arg):
        command = input()
        try:
            process = subprocess.run(command.split(), capture_output=True, check=True, text=True)
            output = process.stdout if process.stdout else ""
            print(output)
        except subprocess.CalledProcessError as error:
            traceback: str = error.stderr if error.stderr else str(error)
            error_information = str(error)
            print(traceback)
            print(error_information)
        except FileNotFoundError as e:
            print(e)

    def do_send(self, arg):
        """Send a command to the terminal"""
        if not self.child_terminal or not self.child_terminal.is_terminal_active():
            click.echo("No active terminal session. Use 'start' first.")
            return
        response = self.child_terminal.send_to_terminal(arg)
        if response:
            click.echo(f"Command sent: {response}")
    def do_quit(self, arg):
        """Exit the application"""
        return self.do_exit(arg)

    # Shortcut for exit
    do_EOF = do_quit

    def default(self, line):
        """Handle unknown commands"""
        if self.child_terminal and self.child_terminal.is_terminal_active():
            self.do_send(line)
        else:
            click.echo(f"Unknown command: {line}")
        click.echo(f"Unknown command: {line}")
    def precmd(self, line):
            """Check terminal status before each command"""
            if self.child_terminal and not self.child_terminal.is_terminal_active():
                click.echo("Terminal session ended unexpectedly")
            return line

@click.group(invoke_without_command=True)
@click.pass_context
def cli(ctx):
    """Zap CLI - An interactive command line tool"""
    if ctx.invoked_subcommand is None:
        # Start the interactive shell
        shell = ZapShell()
        shell.ctx = ctx
        shell.cmdloop()


@cli.command()
def version():
    """Show the version"""
    click.echo('Zap CLI v0.1.0')

def main():
    try:
        cli()
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
        sys.exit(0)

if __name__ == '__main__':
    main()
