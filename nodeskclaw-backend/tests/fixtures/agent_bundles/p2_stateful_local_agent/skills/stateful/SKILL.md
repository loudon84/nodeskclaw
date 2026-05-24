---
name: stateful-local
version: 1.0.0
description: Uses local state and a relative script
scripts:
  run: scripts/run_stateful.py
permissions:
  tools: ["bash_tool", "filesystem"]
---

# Stateful Local

Use `scripts/run_stateful.py` from the restored bundle directory.
