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
    COMMITTED_IMAGE = "localhost/podman-sandbox:committed"

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
            "auto_commit": False,
        }

    def _save_config(self):
        """Save configuration to file."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(self.CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)

    def configure(self, memory_limit: Optional[str] = None, image: Optional[str] = None, auto_commit: Optional[bool] = None):
        """Configure container settings."""
        if memory_limit is not None:
            self.config["memory_limit"] = memory_limit
        if image is not None:
            self.config["image"] = image
        if auto_commit is not None:
            self.config["auto_commit"] = auto_commit
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

    def _committed_image_exists(self) -> bool:
        """Check if a committed image exists."""
        try:
            result = subprocess.run(
                ["podman", "image", "exists", self.COMMITTED_IMAGE],
                capture_output=True,
                check=False,
            )
            return result.returncode == 0
        except subprocess.CalledProcessError:
            return False

    def _get_image_to_use(self) -> str:
        """Determine which image to use: committed if it exists, otherwise base image."""
        if self._committed_image_exists():
            return self.COMMITTED_IMAGE
        return self.config["image"]

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
            "-v", f"{current_dir}:/workspace",  # Mount current directory (rootless-friendly)
            "-w", "/workspace",  # Set working directory
        ]

        # Add memory limit if configured
        if self.config.get("memory_limit"):
            cmd.extend(["-m", self.config["memory_limit"]])

        # Use committed image if it exists, otherwise use configured image
        image_to_use = self._get_image_to_use()
        cmd.extend([image_to_use, "sleep", "infinity"])

        # Start container
        subprocess.run(cmd, capture_output=True, check=True)

    def stop(self, skip_commit: bool = False):
        """Stop the sandbox container.

        Args:
            skip_commit: If True, skip auto-commit even if enabled in config
        """
        if not self.is_running():
            raise RuntimeError(f"Container '{self.CONTAINER_NAME}' is not running")

        # Auto-commit if enabled in config
        committed = False
        if self.config.get("auto_commit", False) and not skip_commit:
            try:
                self.commit()
                committed = True
            except Exception:
                # Don't fail stop if commit fails, just skip it
                pass

        subprocess.run(
            ["podman", "stop", self.CONTAINER_NAME],
            capture_output=True,
            check=True,
        )

        return committed

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
                "-v", f"{current_dir}:/workspace",
                "-w", "/workspace",
            ]

            if self.config.get("memory_limit"):
                restart_cmd.extend(["-m", self.config["memory_limit"]])

            image_to_use = self._get_image_to_use()
            restart_cmd.extend([image_to_use, "sleep", "infinity"])

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

    def commit(self) -> str:
        """Commit the current container state to an image.

        Returns:
            The name of the committed image

        Raises:
            RuntimeError: If container is not running or commit fails
        """
        if not self.is_running():
            raise RuntimeError(f"Container '{self.CONTAINER_NAME}' is not running")

        try:
            # If old committed image exists, we need to remove it first
            # But we can't remove it if a container is using it, so we remove containers first
            if self._committed_image_exists():
                # Find all containers using the committed image
                result = subprocess.run(
                    ["podman", "ps", "-a", "--filter", f"ancestor={self.COMMITTED_IMAGE}", "--format", "{{.Names}}"],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                # Remove containers using the old committed image (except the current one)
                for container_name in result.stdout.strip().split("\n"):
                    if container_name and container_name != self.CONTAINER_NAME:
                        subprocess.run(
                            ["podman", "rm", "-f", container_name],
                            capture_output=True,
                            check=False,
                        )

                # Now remove the old committed image
                subprocess.run(
                    ["podman", "rmi", "-f", self.COMMITTED_IMAGE],
                    capture_output=True,
                    check=False,  # Don't fail if image can't be removed
                )

            # Commit current container state
            subprocess.run(
                ["podman", "commit", self.CONTAINER_NAME, self.COMMITTED_IMAGE],
                capture_output=True,
                check=True,
            )
            return self.COMMITTED_IMAGE
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to commit container: {e}")

    def reset(self) -> bool:
        """Remove the committed image and revert to base image.

        Returns:
            True if reset was successful, False if no committed image existed

        Raises:
            RuntimeError: If reset fails
        """
        if not self._committed_image_exists():
            return False

        try:
            # If container exists (even if stopped), remove it first
            # because it references the committed image
            if self.exists():
                subprocess.run(
                    ["podman", "rm", "-f", self.CONTAINER_NAME],
                    capture_output=True,
                    check=True,
                )

            # Now remove the committed image
            result = subprocess.run(
                ["podman", "rmi", self.COMMITTED_IMAGE],
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Failed to remove image: {result.stderr}")

            return True
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to reset: {e}")
