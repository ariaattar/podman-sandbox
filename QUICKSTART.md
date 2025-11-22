# Quick Start Guide

## Installation

```bash
pip install -e .
```

## Basic Workflow

### 1. Just run commands! (auto-starts)
```bash
# List files in current directory (auto-starts if not running)
podman-sandbox execute "ls -la"

# Run a Python script (if Alpine has Python installed)
podman-sandbox execute "python examples/helloworld.py"

# Interactive shell
podman-sandbox execute -i "sh"
```

**The container automatically:**
- Starts if not running
- Remounts when you change directories
- Stays running for fast repeated executions

### 3. Configure resources
```bash
# Set memory limit
podman-sandbox configure --memory 512m

# Change to Python image
podman-sandbox configure --image python:3.11-alpine

# View current config
podman-sandbox configure --show
```

### 4. Check status
```bash
podman-sandbox status
```

### 5. List all containers
```bash
podman-sandbox list
```

### 6. Stop when done
```bash
podman-sandbox stop
```

## Example: Running Python code

```bash
# Configure with Python image
podman-sandbox configure --image python:3.11-alpine

# Restart (or start if not running)
podman-sandbox stop 2>/dev/null || true
podman-sandbox start

# Run your Python script
podman-sandbox execute "python examples/helloworld.py"
```

## Example: Memory-limited execution

```bash
# Set 256MB memory limit
podman-sandbox configure --memory 256m

# Start with the limit
podman-sandbox start

# Run memory-intensive code (will be limited)
podman-sandbox execute "python my_script.py"
```

## Tips

- Current directory is auto-mounted to `/workspace` in the container
- Container stays running for fast repeated executions
- Configuration persists in `~/.config/podman-sandbox/config.json`
- Use `--image` to quickly test code in different environments
