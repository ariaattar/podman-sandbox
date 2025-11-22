"""Tests for the CLI interface."""

import subprocess
import pytest
from click.testing import CliRunner
from podman_sandbox.cli import main


class TestCLI:
    """Test the CLI commands."""

    def setup_method(self):
        """Setup test fixtures."""
        self.runner = CliRunner()
        # Clean up any existing containers
        subprocess.run(
            ["podman", "rm", "-f", "podman-sandbox"],
            capture_output=True,
        )

    def teardown_method(self):
        """Cleanup after tests."""
        subprocess.run(
            ["podman", "rm", "-f", "podman-sandbox"],
            capture_output=True,
        )

    def test_version(self):
        """Test version command."""
        result = self.runner.invoke(main, ["--version"])
        assert result.exit_code == 0

    def test_configure_show(self):
        """Test configure --show command."""
        result = self.runner.invoke(main, ["configure", "--show"])
        assert result.exit_code == 0
        assert "Current configuration:" in result.output

    def test_configure_memory(self):
        """Test configure --memory command."""
        result = self.runner.invoke(main, ["configure", "--memory", "512m"])
        assert result.exit_code == 0
        assert "Configuration updated successfully" in result.output

    def test_configure_image(self):
        """Test configure --image command."""
        result = self.runner.invoke(main, ["configure", "--image", "alpine:latest"])
        assert result.exit_code == 0
        assert "Configuration updated successfully" in result.output

    def test_status_when_not_created(self):
        """Test status when container doesn't exist."""
        result = self.runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "not_created" in result.output

    def test_start_and_stop(self):
        """Test starting and stopping the container."""
        # Start container
        result = self.runner.invoke(main, ["start"])
        assert result.exit_code == 0
        assert "started successfully" in result.output

        # Check status
        result = self.runner.invoke(main, ["status"])
        assert result.exit_code == 0
        assert "running: yes" in result.output.lower()

        # Stop container
        result = self.runner.invoke(main, ["stop"])
        assert result.exit_code == 0
        assert "stopped successfully" in result.output

    def test_execute_command(self):
        """Test executing a command in the container."""
        # Start container first
        self.runner.invoke(main, ["start"])

        # Execute a simple command
        result = self.runner.invoke(main, ["execute", "echo 'Hello from sandbox'"])
        assert result.exit_code == 0

        # Clean up
        self.runner.invoke(main, ["stop"])

    def test_execute_without_starting(self):
        """Test that execute fails if container is not running."""
        result = self.runner.invoke(main, ["execute", "ls"])
        assert result.exit_code == 1
        assert "not running" in result.output

    def test_start_twice_fails(self):
        """Test that starting an already running container fails."""
        # Start first time
        self.runner.invoke(main, ["start"])

        # Try to start again
        result = self.runner.invoke(main, ["start"])
        assert result.exit_code == 1
        assert "already running" in result.output.lower()

        # Clean up
        self.runner.invoke(main, ["stop"])

    def test_list_containers(self):
        """Test listing containers."""
        result = self.runner.invoke(main, ["list"])
        assert result.exit_code == 0

    def test_list_with_sandbox_running(self):
        """Test listing containers when sandbox is running."""
        # Start sandbox
        self.runner.invoke(main, ["start"])

        # List containers
        result = self.runner.invoke(main, ["list"])
        assert result.exit_code == 0
        assert "podman-sandbox" in result.output
        assert "[SANDBOX]" in result.output

        # Clean up
        self.runner.invoke(main, ["stop"])
