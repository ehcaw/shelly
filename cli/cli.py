import click
import sys
import cmd
from process_monitor import ProcessMonitor
from listener import Listener
from child_terminal import ChildTerminal

class ZapShell(cmd.Cmd):
    intro = 'Welcome to the Zap CLI. Type help or ? to list commands.\n'
    prompt = 'zap> '

    def __init__(self):
        super().__init__()
        self.ctx = None
        self.zapper = None
        self.child_terminal = None

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
        self.zapper = Listener()
        self.zapper.start()
        #self.zapper.run_subscriber()
        self.child_terminal= ChildTerminal(session_name='zapper_session')
        if self.child_terminal.open_new_terminal():
            self.child_terminal.monitor = ProcessMonitor(self.child_terminal)
            self.child_terminal.monitor.start_monitoring()
            click.echo("tmux session and monitoring started successfully")
            #self.term_sesh.publisher.send_json({'type': 'info', 'data': 'tmux session started'})
        else:
            click.echo("Failed to start terminal session")



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
