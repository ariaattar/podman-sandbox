#!/usr/bin/env python3
"""Script to deliberately exhaust memory to test podman-sandbox memory limit (512MB)."""

import sys

print("Memory stress test: Attempting to allocate lots of memory inside the sandbox...", flush=True)

mem_chunks = []
try:
    i = 0
    while True:
        # Allocate 10MB per step, so we hit 512MB quickly.
        mem_chunks.append(bytearray(10 * 1024 * 1024))
        i += 1
        if i % 10 == 0:
            print(f"Allocated {i*10}MB so far...", flush=True)
except MemoryError:
    print("MemoryError caught! The sandbox memory limit was reached.", flush=True)
    print(f"Stopped after allocating approximately {i*10}MB.", flush=True)
    sys.exit(42)

print("Finished without hitting the memory limit? This is unexpected!")
