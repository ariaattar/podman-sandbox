# Podman Sandbox

A lightweight CLI tool for sandboxing code execution in Podman containers.

## Features

- **Easy container management**: Start/stop sandbox containers with simple commands
- **Execute code safely**: Run commands and scripts in isolated containers
- **Persistent state**: Commit container state to preserve installed packages across restarts
- **Rootless mode**: Run containers without root privileges for better security
- **Resource limits**: Configure memory limits for sandboxed execution
- **Automatic mounting**: Your current directory is automatically mounted into the container
- **Multiple image support**: Use any container image (Alpine, Python, Node.js, etc.)

## Installation

### Using pip

```bash
pip install -e .
```

### Using uv

```bash
uv pip install -e .
```

## Quick Start

### 1. Execute commands (auto-starts if needed!)

```bash
# Run a simple command (automatically starts container if not running)
podman-sandbox execute "ls -la"

# Run a Python script
podman-sandbox execute "python helloworld.py"

# Run an interactive shell
podman-sandbox execute -i "sh"
```

**No need to manually start!** The container automatically starts when you first execute a command, and automatically remounts if you change directories.

### 2. Or manually start the sandbox container

```bash
podman-sandbox start
```

This creates a lightweight Alpine Linux container with your current directory mounted at `/workspace`.

### 3. Configure the sandbox

```bash
# Set memory limit (automatically restarts if running)
podman-sandbox configure --memory 512m

# Use a different image (automatically restarts if running)
podman-sandbox configure --image python:3.11-alpine

# Show current configuration
podman-sandbox configure --show

# Change settings without auto-restart
podman-sandbox configure --memory 1g --no-restart
```

The `configure` command will:
- Show a pretty diff of what changed
- Automatically stop and restart the container if it's running
- Apply changes immediately

### 4. Check status

```bash
podman-sandbox status
```

### 5. List all containers

```bash
podman-sandbox list
```

This shows all Podman containers and marks which one is being used as the sandbox.

### 6. Stop the sandbox

```bash
podman-sandbox stop
```

### 7. Persist installed packages (NEW!)

By default, packages installed in the container disappear when you restart. You have two options to make them persist:

#### Option 1: Manual commit (default)

```bash
# Install packages
podman-sandbox execute "pip install uv"
podman-sandbox execute "apk add git curl"

# Save the container state
podman-sandbox commit

# Now packages persist across restarts!
podman-sandbox stop
podman-sandbox start
podman-sandbox execute "uv --version"  # ✓ Still works!

# To go back to a fresh container
podman-sandbox reset
```

#### Option 2: Auto-commit (recommended for convenience)

Enable auto-commit to automatically save state when stopping:

```bash
# Enable auto-commit once
podman-sandbox configure --auto-commit

# Now you don't need to manually commit!
podman-sandbox execute "pip install uv"
podman-sandbox stop  # ✓ Automatically commits before stopping!
podman-sandbox start
podman-sandbox execute "uv --version"  # ✓ Still works!

# Disable auto-commit if needed
podman-sandbox configure --no-auto-commit
```

## Usage Examples

### Basic command execution

```bash
# Start container
podman-sandbox start

# List files
podman-sandbox execute "ls"

# Check memory usage
podman-sandbox execute "free -m"

# Stop container
podman-sandbox stop
```

### Running Python scripts

```bash
# Configure to use Python image (auto-restarts if running)
podman-sandbox configure --image python:3.11-alpine

# Run a Python script
podman-sandbox execute "python examples/helloworld.py"
```

### Persisting packages across restarts

```bash
# Install uv once
podman-sandbox execute "pip install uv"

# Save the state so uv persists
podman-sandbox commit

# Now uv is available even after restart!
podman-sandbox stop && podman-sandbox start
podman-sandbox execute "uv run helloworld.py"
```

### Memory limits

```bash
# Set memory limit to 512MB (auto-restarts if running)
podman-sandbox configure --memory 512m

# Verify memory limit
podman-sandbox status
```

### Interactive sessions

```bash
# Start an interactive shell
podman-sandbox execute -i "sh"

# Or with bash if available
podman-sandbox execute -i "bash"
```

## Commands

### `podman-sandbox start`

Start the sandbox container. Creates a new container if one doesn't exist.

Options:
- `--image IMAGE`: Specify container image to use

### `podman-sandbox stop`

Stop the running sandbox container.

### `podman-sandbox execute COMMAND`

Execute a command inside the sandbox container. Automatically starts the container if not running and remounts if you've changed directories.

Options:
- `-i, --interactive`: Run in interactive mode (for shells, etc.)

### `podman-sandbox configure`

Configure sandbox settings. Automatically restarts the container if it's running to apply changes immediately.

Options:
- `--memory, -m LIMIT`: Set memory limit (e.g., '512m', '1g')
- `--image IMAGE`: Set container image
- `--auto-commit`: Enable auto-commit (automatically save state on stop)
- `--no-auto-commit`: Disable auto-commit
- `--show`: Show current configuration
- `--no-restart`: Don't automatically restart the container

### `podman-sandbox status`

Show current status of the sandbox container and configuration.

### `podman-sandbox list`

List all Podman containers and identify which one is being used as the sandbox.

### `podman-sandbox commit`

Save the current container state to preserve installed packages and modifications.

**Important:** This is required for packages to persist across container restarts!

Example:
```bash
podman-sandbox execute "pip install uv"
podman-sandbox commit  # Save the state
podman-sandbox stop && podman-sandbox start
podman-sandbox execute "uv --version"  # ✓ Still works!
```

### `podman-sandbox reset`

Remove the saved container state and revert to the base image.

After running this, the next container start will use a fresh base image without any installed packages.

Example:
```bash
podman-sandbox reset  # Remove saved state
podman-sandbox start  # Fresh container
```

## Configuration

Configuration is stored in `~/.config/podman-sandbox/config.json`.

Default settings:
- **Image**: `alpine:latest`
- **Memory limit**: unlimited

## Performance with crun

Good news! **Podman already uses `crun` by default** on most systems, which means you're already getting optimal performance!

You can verify this by running:
```bash
podman info | grep -A 5 ociRuntime
```

### crun Performance Benefits

crun provides significantly better performance than runc:
- **~50% faster** container startup times
- **Much lower memory footprint**
- Can run containers with stricter memory limits (down to 512KB)

### Benchmark Comparison

Running 100 sequential containers with `/bin/true`:
- **runc**: 3.34 seconds
- **crun**: 1.69 seconds (-49.4%)

Since podman-sandbox automatically uses Podman's configured runtime (which is typically crun), you're already benefiting from these performance improvements!

## How It Works

1. **Container Creation**: Creates a Podman container in detached mode with `sleep infinity` to keep it running
2. **Volume Mounting**: Mounts your current working directory to `/workspace` in the container
3. **Auto-Start**: Automatically starts the container when you execute a command if not running
4. **Dynamic Remounting**: Detects when you've changed directories and automatically remounts the new directory
5. **Command Execution**: Uses `podman exec` to run commands inside the container
6. **Persistence**: The container stays running until you stop it, allowing fast repeated executions

## Requirements

- Podman installed and configured
- Python 3.8 or higher

## Testing

Run the test suite:

```bash
pytest tests/
```

## Troubleshooting

### Container won't start
- Check that Podman is installed: `podman --version`
- Ensure Podman service is running: `podman ps`

### Command execution fails
- Verify the container is running: `podman-sandbox status`
- Start the container if needed: `podman-sandbox start`

### Permission issues
- Podman may need SELinux labels on volumes (`:Z` flag is automatically added)
- Check Podman logs: `podman logs podman-sandbox`

## License

MIT
