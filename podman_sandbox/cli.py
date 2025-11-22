"""CLI interface for podman-sandbox."""

import sys
import click
from .container import PodmanContainer


@click.group()
@click.version_option()
def main():
    """Podman Sandbox - Easily sandbox code execution in Podman containers."""
    pass


@main.command()
@click.option("--image", default=None, help="Container image to use (default: alpine:latest)")
def start(image):
    """Start the sandbox container."""
    container = PodmanContainer()

    if image:
        container.configure(image=image)

    try:
        container.start()
        click.echo(click.style("✓ Sandbox container started successfully", fg='green', bold=True))
        click.echo(f"  Image: {click.style(container.config['image'], fg='blue')}")
        click.echo(f"  Working directory: {click.style('/workspace', fg='cyan')} (mounted from {container.CONFIG_DIR.parent.parent})")
        if container.config.get("memory_limit"):
            click.echo(f"  Memory limit: {click.style(container.config['memory_limit'], fg='cyan')}")
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to start container: {e}", err=True)
        sys.exit(1)


@main.command()
def stop():
    """Stop the sandbox container.

    If auto-commit is enabled, the container state will be automatically
    saved before stopping.
    """
    container = PodmanContainer()

    try:
        committed = container.stop()
        if committed:
            click.echo(click.style("✓ Container state saved automatically", fg='green'))
        click.echo(click.style("✓ Sandbox container stopped successfully", fg='green', bold=True))
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to stop container: {e}", err=True)
        sys.exit(1)


@main.command()
@click.argument("command")
@click.option("-i", "--interactive", is_flag=True, help="Run in interactive mode")
def execute(command, interactive):
    """Execute a command in the sandbox container.

    The container automatically starts if not running and remounts if you've changed directories.

    Examples:
        sandbox execute "ls -la"
        sandbox execute "python helloworld.py"
        sandbox execute -i "bash"
    """
    container = PodmanContainer()

    try:
        import os
        current_dir = os.getcwd()

        # Auto-start if not running
        if not container.is_running():
            click.echo(click.style("Container not running, starting...", fg='yellow'))
            container.start()
            click.echo("")

        # Check if we need to restart for directory change
        mounted_dir = container.get_mounted_directory()
        if mounted_dir and mounted_dir != current_dir and container.is_running():
            click.echo(click.style("Directory changed, restarting container...", fg='yellow'))
            click.echo(f"  Old: {click.style(mounted_dir, fg='red')}")
            click.echo(f"  New: {click.style(current_dir, fg='green')}")

        result = container.execute(command, interactive=interactive)
        sys.exit(result.returncode)
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to execute command: {e}", err=True)
        sys.exit(1)


@main.command()
@click.option("--memory", "-m", help="Set memory limit (e.g., '512m', '1g')")
@click.option("--image", help="Set container image (e.g., 'python:3.11-alpine')")
@click.option("--auto-commit/--no-auto-commit", default=None, help="Enable/disable auto-commit on stop")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--no-restart", is_flag=True, help="Don't restart the container automatically")
def configure(memory, image, auto_commit, show, no_restart):
    """Configure sandbox container settings.

    Examples:
        sandbox configure --memory 512m
        sandbox configure --image python:3.11-alpine
        sandbox configure --auto-commit  # Enable auto-commit
        sandbox configure --no-auto-commit  # Disable auto-commit
        sandbox configure --show
    """
    container = PodmanContainer()

    if show:
        click.echo(click.style("Current configuration:", bold=True))
        click.echo(f"  Image: {click.style(container.config['image'], fg='blue')}")
        click.echo(f"  Memory limit: {click.style(container.config.get('memory_limit') or 'unlimited', fg='blue')}")
        auto_commit_status = "enabled" if container.config.get('auto_commit', False) else "disabled"
        auto_commit_color = 'green' if container.config.get('auto_commit', False) else 'yellow'
        click.echo(f"  Auto-commit: {click.style(auto_commit_status, fg=auto_commit_color)}")
        return

    if not memory and not image and auto_commit is None:
        click.echo("Error: No configuration options provided", err=True)
        click.echo("Use --memory, --image, --auto-commit, or --show to view current config")
        sys.exit(1)

    try:
        # Store old config for comparison
        old_config = {
            "image": container.config['image'],
            "memory_limit": container.config.get('memory_limit') or 'unlimited',
            "auto_commit": container.config.get('auto_commit', False)
        }

        # Update configuration
        container.configure(memory_limit=memory, image=image, auto_commit=auto_commit)

        # New config after update
        new_config = {
            "image": container.config['image'],
            "memory_limit": container.config.get('memory_limit') or 'unlimited',
            "auto_commit": container.config.get('auto_commit', False)
        }

        # Display pretty diff with colors
        click.echo(click.style("Configuration changes:", bold=True))
        click.echo("")

        if old_config['image'] != new_config['image']:
            click.echo(f"  {click.style('Image:', bold=True)}")
            click.echo(f"    {click.style('-', fg='red')} {click.style(old_config['image'], fg='red')}")
            click.echo(f"    {click.style('+', fg='green')} {click.style(new_config['image'], fg='green')}")
        else:
            click.echo(f"  Image: {click.style(new_config['image'], fg='blue')} {click.style('(unchanged)', fg='bright_black')}")

        if old_config['memory_limit'] != new_config['memory_limit']:
            click.echo(f"  {click.style('Memory limit:', bold=True)}")
            click.echo(f"    {click.style('-', fg='red')} {click.style(old_config['memory_limit'], fg='red')}")
            click.echo(f"    {click.style('+', fg='green')} {click.style(new_config['memory_limit'], fg='green')}")
        else:
            click.echo(f"  Memory limit: {click.style(new_config['memory_limit'], fg='blue')} {click.style('(unchanged)', fg='bright_black')}")

        if old_config['auto_commit'] != new_config['auto_commit']:
            click.echo(f"  {click.style('Auto-commit:', bold=True)}")
            old_status = "enabled" if old_config['auto_commit'] else "disabled"
            new_status = "enabled" if new_config['auto_commit'] else "disabled"
            click.echo(f"    {click.style('-', fg='red')} {click.style(old_status, fg='red')}")
            click.echo(f"    {click.style('+', fg='green')} {click.style(new_status, fg='green')}")
        else:
            auto_status = "enabled" if new_config['auto_commit'] else "disabled"
            click.echo(f"  Auto-commit: {click.style(auto_status, fg='blue')} {click.style('(unchanged)', fg='bright_black')}")

        click.echo("")

        # Auto-restart if container is running
        was_running = container.is_running()

        if was_running and not no_restart:
            click.echo(click.style("Restarting container to apply changes...", fg='yellow'))
            try:
                container.stop(skip_commit=True)  # Skip auto-commit during config restart
                click.echo(f"  {click.style('✓', fg='green')} Container stopped")
                container.start()
                click.echo(f"  {click.style('✓', fg='green')} Container started with new configuration")
                click.echo("")
                click.echo(click.style("Configuration applied successfully!", fg='green', bold=True))
            except Exception as e:
                click.echo(f"  {click.style('✗', fg='red')} Failed to restart: {e}", err=True)
                click.echo("  Run 'sandbox stop && sandbox start' manually")
                sys.exit(1)
        elif was_running and no_restart:
            click.echo(click.style("Container is running but --no-restart was specified.", fg='yellow'))
            click.echo("Restart manually to apply changes:")
            click.echo(f"  {click.style('sandbox stop && sandbox start', fg='cyan')}")
        else:
            click.echo(click.style("Container is not running.", fg='yellow') + " Start it to use the new configuration:")
            click.echo(f"  {click.style('sandbox start', fg='cyan')}")

    except Exception as e:
        click.echo(f"Failed to update configuration: {e}", err=True)
        sys.exit(1)


@main.command()
def status():
    """Show sandbox container status."""
    container = PodmanContainer()

    try:
        info = container.status()
        click.echo(click.style("Sandbox container status:", bold=True))

        # Color status based on running state
        status_text = info['status']
        if info['running']:
            status_color = 'green'
            running_color = 'green'
        else:
            status_color = 'yellow'
            running_color = 'red'

        click.echo(f"  Status: {click.style(status_text, fg=status_color)}")
        click.echo(f"  Running: {click.style('yes' if info['running'] else 'no', fg=running_color)}")

        if info.get("started_at"):
            click.echo(f"  Started at: {click.style(info['started_at'], fg='cyan')}")
        if info.get("memory_limit"):
            click.echo(f"  Memory limit: {click.style(info['memory_limit'], fg='cyan')}")

        click.echo(f"\n{click.style('Configuration:', bold=True)}")
        click.echo(f"  Image: {click.style(container.config['image'], fg='blue')}")
        click.echo(f"  Memory limit: {click.style(container.config.get('memory_limit') or 'unlimited', fg='blue')}")
        auto_commit_status = "enabled" if container.config.get('auto_commit', False) else "disabled"
        auto_commit_color = 'green' if container.config.get('auto_commit', False) else 'yellow'
        click.echo(f"  Auto-commit: {click.style(auto_commit_status, fg=auto_commit_color)}")
    except Exception as e:
        click.echo(f"Failed to get status: {e}", err=True)
        sys.exit(1)


@main.command()
def list():
    """List all Podman containers and identify the sandbox container."""
    container = PodmanContainer()

    try:
        containers = container.list_all_containers()

        if not containers:
            click.echo(click.style("No containers found.", fg='yellow'))
            return

        click.echo(click.style("All Podman containers:", bold=True))
        click.echo("")

        for c in containers:
            marker = f" {click.style('[SANDBOX]', fg='green', bold=True)}" if c["is_sandbox"] else ""
            click.echo(f"  {click.style(c['name'], fg='cyan', bold=True)}{marker}")
            click.echo(f"    Image:   {click.style(c['image'], fg='blue')}")

            # Color status based on state
            status_color = 'green' if 'running' in c['status'].lower() else 'yellow'
            click.echo(f"    Status:  {click.style(c['status'], fg=status_color)}")
            click.echo(f"    Created: {c['created']}")
            click.echo("")

    except Exception as e:
        click.echo(f"Failed to list containers: {e}", err=True)
        sys.exit(1)


@main.command()
def commit():
    """Save the current container state to preserve installed packages.

    This commits the running container to a local image. When the container
    is restarted, it will use this saved state, preserving any packages you've
    installed.

    Examples:
        # Install packages
        sandbox execute "apk add python3 git"

        # Save the state
        sandbox commit

        # Now when you restart, packages are still there
        sandbox stop && sandbox start
    """
    container = PodmanContainer()

    try:
        click.echo(click.style("Committing container state...", fg='yellow'))
        image_name = container.commit()
        click.echo(click.style(f"✓ Container state saved to: {image_name}", fg='green', bold=True))
        click.echo("")
        click.echo("The container will now use this saved state when restarted.")
        click.echo(f"To revert to the base image, run: {click.style('sandbox reset', fg='cyan')}")
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to commit container: {e}", err=True)
        sys.exit(1)


@main.command()
def reset():
    """Remove saved container state and revert to base image.

    This deletes the committed image, so the next time you start the container
    it will be fresh from the base image (without any installed packages).

    Examples:
        sandbox reset
    """
    container = PodmanContainer()

    try:
        if container.reset():
            click.echo(click.style("✓ Saved state removed", fg='green', bold=True))
            click.echo("")
            click.echo("The container will use the base image on next start.")
            if container.is_running():
                click.echo(click.style("Note: ", fg='yellow') + "Container is still running with old state.")
                click.echo(f"Restart to use base image: {click.style('sandbox stop && sandbox start', fg='cyan')}")
        else:
            click.echo(click.style("No saved state found", fg='yellow'))
    except Exception as e:
        click.echo(f"Failed to reset: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
