#!/usr/bin/env python3
"""A simple hello world script to test podman-sandbox."""

print("Hello from the sandbox!")
print("This Python script is running inside a Podman container.")

# Show we can access the filesystem
import os
print(f"\nCurrent directory: {os.getcwd()}")
print(f"Files in current directory:")
for item in os.listdir("."):
    print(f"  - {item}")
