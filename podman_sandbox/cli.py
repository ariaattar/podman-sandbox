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
        click.echo(f"✓ Sandbox container started successfully")
        click.echo(f"  Image: {container.config['image']}")
        click.echo(f"  Working directory: /workspace (mounted from {container.CONFIG_DIR.parent.parent})")
        if container.config.get("memory_limit"):
            click.echo(f"  Memory limit: {container.config['memory_limit']}")
    except RuntimeError as e:
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"Failed to start container: {e}", err=True)
        sys.exit(1)


@main.command()
def stop():
    """Stop the sandbox container."""
    container = PodmanContainer()

    try:
        container.stop()
        click.echo("✓ Sandbox container stopped successfully")
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
        podman-sandbox execute "ls -la"
        podman-sandbox execute "python helloworld.py"
        podman-sandbox execute -i "bash"
    """
    container = PodmanContainer()

    try:
        import os
        current_dir = os.getcwd()

        # Auto-start if not running
        if not container.is_running():
            click.echo("Container not running, starting...")
            container.start()
            click.echo("")

        # Check if we need to restart for directory change
        mounted_dir = container.get_mounted_directory()
        if mounted_dir and mounted_dir != current_dir and container.is_running():
            click.echo(f"Directory changed, restarting container...")
            click.echo(f"  Old: {mounted_dir}")
            click.echo(f"  New: {current_dir}")

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
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--no-restart", is_flag=True, help="Don't restart the container automatically")
def configure(memory, image, show, no_restart):
    """Configure sandbox container settings.

    Examples:
        podman-sandbox configure --memory 512m
        podman-sandbox configure --image python:3.11-alpine
        podman-sandbox configure --show
    """
    container = PodmanContainer()

    if show:
        click.echo("Current configuration:")
        click.echo(f"  Image: {container.config['image']}")
        click.echo(f"  Memory limit: {container.config.get('memory_limit') or 'unlimited'}")
        return

    if not memory and not image:
        click.echo("Error: No configuration options provided", err=True)
        click.echo("Use --memory or --image, or --show to view current config")
        sys.exit(1)

    try:
        # Store old config for comparison
        old_config = {
            "image": container.config['image'],
            "memory_limit": container.config.get('memory_limit') or 'unlimited'
        }

        # Update configuration
        container.configure(memory_limit=memory, image=image)

        # New config after update
        new_config = {
            "image": container.config['image'],
            "memory_limit": container.config.get('memory_limit') or 'unlimited'
        }

        # Display pretty diff
        click.echo("Configuration changes:")
        click.echo("")

        if old_config['image'] != new_config['image']:
            click.echo(f"  Image:")
            click.echo(f"    - {old_config['image']}")
            click.echo(f"    + {new_config['image']}")
        else:
            click.echo(f"  Image: {new_config['image']} (unchanged)")

        if old_config['memory_limit'] != new_config['memory_limit']:
            click.echo(f"  Memory limit:")
            click.echo(f"    - {old_config['memory_limit']}")
            click.echo(f"    + {new_config['memory_limit']}")
        else:
            click.echo(f"  Memory limit: {new_config['memory_limit']} (unchanged)")

        click.echo("")

        # Auto-restart if container is running
        was_running = container.is_running()

        if was_running and not no_restart:
            click.echo("Restarting container to apply changes...")
            try:
                container.stop()
                click.echo("  ✓ Container stopped")
                container.start()
                click.echo("  ✓ Container started with new configuration")
                click.echo("")
                click.echo("Configuration applied successfully!")
            except Exception as e:
                click.echo(f"  ✗ Failed to restart: {e}", err=True)
                click.echo("  Run 'podman-sandbox stop && podman-sandbox start' manually")
                sys.exit(1)
        elif was_running and no_restart:
            click.echo("Container is running but --no-restart was specified.")
            click.echo("Restart manually to apply changes:")
            click.echo("  podman-sandbox stop && podman-sandbox start")
        else:
            click.echo("Container is not running. Start it to use the new configuration:")
            click.echo("  podman-sandbox start")

    except Exception as e:
        click.echo(f"Failed to update configuration: {e}", err=True)
        sys.exit(1)


@main.command()
def status():
    """Show sandbox container status."""
    container = PodmanContainer()

    try:
        info = container.status()
        click.echo("Sandbox container status:")
        click.echo(f"  Status: {info['status']}")
        click.echo(f"  Running: {'yes' if info['running'] else 'no'}")

        if info.get("started_at"):
            click.echo(f"  Started at: {info['started_at']}")
        if info.get("memory_limit"):
            click.echo(f"  Memory limit: {info['memory_limit']}")

        click.echo(f"\nConfiguration:")
        click.echo(f"  Image: {container.config['image']}")
        click.echo(f"  Memory limit: {container.config.get('memory_limit') or 'unlimited'}")
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
            click.echo("No containers found.")
            return

        click.echo("All Podman containers:")
        click.echo("")

        for c in containers:
            marker = " [SANDBOX]" if c["is_sandbox"] else ""
            click.echo(f"  {c['name']}{marker}")
            click.echo(f"    Image:   {c['image']}")
            click.echo(f"    Status:  {c['status']}")
            click.echo(f"    Created: {c['created']}")
            click.echo("")

    except Exception as e:
        click.echo(f"Failed to list containers: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
