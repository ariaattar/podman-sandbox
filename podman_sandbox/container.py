"""Container management for podman-sandbox."""

import json
import os
import subprocess
from pathlib import Path
from typing import Optional


class PodmanContainer:
    """Manages the podman sandbox container lifecycle."""

    CONFIG_DIR = Path.home() / ".config" / "podman-sandbox"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    CONTAINER_NAME = "podman-sandbox"
    DEFAULT_IMAGE = "alpine:latest"

    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load configuration from file."""
        if self.CONFIG_FILE.exists():
            with open(self.CONFIG_FILE, "r") as f:
                return json.load(f)
        return {
            "memory_limit": None,
            "image": self.DEFAULT_IMAGE,
        }

    def _save_config(self):
        """Save configuration to file."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def configure(self, memory_limit: Optional[str] = None, image: Optional[str] = None):
        """Configure container settings."""
        if memory_limit:
            self.config["memory_limit"] = memory_limit
        if image:
            self.config["image"] = image
        self._save_config()

    def is_running(self) -> bool:
        """Check if the sandbox container is running."""
        try:
            result = subprocess.run(
                ["podman", "ps", "--filter", f"name={self.CONTAINER_NAME}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            return self.CONTAINER_NAME in result.stdout
        except subprocess.CalledProcessError:
            return False

    def exists(self) -> bool:
        """Check if the sandbox container exists (running or stopped)."""
        try:
            result = subprocess.run(
                ["podman", "ps", "-a", "--filter", f"name={self.CONTAINER_NAME}", "--format", "{{.Names}}"],
                capture_output=True,
                text=True,
                check=True,
            )
            return self.CONTAINER_NAME in result.stdout
        except subprocess.CalledProcessError:
            return False

    def get_mounted_directory(self) -> Optional[str]:
        """Get the currently mounted directory in the container."""
        if not self.is_running():
            return None

        try:
            result = subprocess.run(
                [
                    "podman", "inspect", self.CONTAINER_NAME,
                    "--format", "{{range .Mounts}}{{if eq .Destination \"/workspace\"}}{{.Source}}{{end}}{{end}}"
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip() or None
        except subprocess.CalledProcessError:
            return None

    def _ensure_image_exists(self, image: str) -> bool:
        """Check if image exists locally, pull if not."""
        try:
            result = subprocess.run(
                ["podman", "image", "exists", image],
                capture_output=True,
                check=False,
            )
            if result.returncode == 0:
                return True  # Image exists, no pull needed

            # Image doesn't exist, pull it
            subprocess.run(
                ["podman", "pull", image],
                capture_output=True,
                check=True,
            )
            return True
        except subprocess.CalledProcessError:
            return False

    def start(self, force_restart: bool = False):
        """Start the sandbox container.

        Args:
            force_restart: If True, restart even if already running with different directory
        """
        current_dir = os.getcwd()

        # Check if container is running with a different directory
        if self.is_running():
            mounted_dir = self.get_mounted_directory()
            if mounted_dir and mounted_dir != current_dir:
                if not force_restart:
                    raise RuntimeError(
                        f"Container '{self.CONTAINER_NAME}' is already running with a different directory.\n"
                        f"  Mounted: {mounted_dir}\n"
                        f"  Current: {current_dir}\n"
                        f"Run 'podman-sandbox stop && podman-sandbox start' to remount with current directory."
                    )
                # Fall through to restart with new directory
            elif mounted_dir == current_dir:
                raise RuntimeError(f"Container '{self.CONTAINER_NAME}' is already running")

        # Ensure image exists (only pulls if not present)
        self._ensure_image_exists(self.config["image"])

        # Fast remove if exists (podman rm -f is faster than stop + rm)
        if self.exists():
            subprocess.run(
                ["podman", "rm", "-f", self.CONTAINER_NAME],
                capture_output=True,
                check=True,
            )

        # Build podman run command
        cmd = [
            "podman", "run",
            "-d",  # Detached mode
            "--name", self.CONTAINER_NAME,
            "-v", f"{current_dir}:/workspace:Z",  # Mount current directory
            "-w", "/workspace",  # Set working directory
        ]

        # Add memory limit if configured
        if self.config.get("memory_limit"):
            cmd.extend(["-m", self.config["memory_limit"]])

        # Add image and keep container running
        cmd.extend([self.config["image"], "sleep", "infinity"])

        # Start container
        subprocess.run(cmd, capture_output=True, check=True)

    def stop(self):
        """Stop the sandbox container."""
        if not self.is_running():
            raise RuntimeError(f"Container '{self.CONTAINER_NAME}' is not running")

        subprocess.run(
            ["podman", "stop", self.CONTAINER_NAME],
            capture_output=True,
            check=True,
        )

    def execute(self, command: str, interactive: bool = False, auto_restart: bool = True) -> subprocess.CompletedProcess:
        """Execute a command in the sandbox container.

        Args:
            command: The command to execute
            interactive: Run in interactive mode
            auto_restart: Automatically restart container if directory changed
        """
        current_dir = os.getcwd()

        if not self.is_running():
            raise RuntimeError(
                f"Container '{self.CONTAINER_NAME}' is not running. Start it with 'podman-sandbox start'"
            )

        # Check if the mounted directory matches current directory
        mounted_dir = self.get_mounted_directory()
        if mounted_dir and mounted_dir != current_dir and auto_restart:
            # Fast restart: rm -f (kill+remove) then run
            self._ensure_image_exists(self.config["image"])

            # Fast remove (kills and removes in one operation)
            subprocess.run(
                ["podman", "rm", "-f", self.CONTAINER_NAME],
                capture_output=True,
                check=True,
            )

            restart_cmd = [
                "podman", "run",
                "-d",
                "--name", self.CONTAINER_NAME,
                "-v", f"{current_dir}:/workspace:Z",
                "-w", "/workspace",
            ]

            if self.config.get("memory_limit"):
                restart_cmd.extend(["-m", self.config["memory_limit"]])

            restart_cmd.extend([self.config["image"], "sleep", "infinity"])

            subprocess.run(restart_cmd, capture_output=True, check=True)

        cmd = ["podman", "exec"]

        if interactive:
            cmd.append("-it")

        cmd.extend([self.CONTAINER_NAME, "sh", "-c", command])

        return subprocess.run(cmd, check=False)

    def status(self) -> dict:
        """Get container status information."""
        if not self.exists():
            return {"status": "not_created", "running": False}

        if self.is_running():
            # Get container stats
            try:
                result = subprocess.run(
                    [
                        "podman", "inspect", self.CONTAINER_NAME,
                        "--format", "{{.State.Status}}|{{.State.StartedAt}}|{{.HostConfig.Memory}}"
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                status, started_at, memory = result.stdout.strip().split("|")
                return {
                    "status": status,
                    "running": True,
                    "started_at": started_at,
                    "memory_limit": memory if memory != "0" else "unlimited",
                }
            except subprocess.CalledProcessError:
                return {"status": "error", "running": False}
        else:
            return {"status": "stopped", "running": False}

    def list_all_containers(self) -> list:
        """List all containers and indicate which is the sandbox."""
        try:
            result = subprocess.run(
                [
                    "podman", "ps", "-a",
                    "--format", "{{.Names}}|{{.Image}}|{{.Status}}|{{.CreatedAt}}"
                ],
                capture_output=True,
                text=True,
                check=True,
            )

            containers = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue

                parts = line.split("|")
                if len(parts) >= 4:
                    name, image, status, created = parts[0], parts[1], parts[2], parts[3]
                    containers.append({
                        "name": name,
                        "image": image,
                        "status": status,
                        "created": created,
                        "is_sandbox": name == self.CONTAINER_NAME,
                    })

            return containers
        except subprocess.CalledProcessError:
            return []
