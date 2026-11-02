# Project journal

Decisions, mistakes and what changed.

## Week 1

### Laptop limits (2026-11-02)

- Docker can use 7.6 GB of memory (8,153,624,576 bytes) and 16 CPU threads.
- With the 1.5 GB of free memory the memory check requires, the full setup has about 6.1 GB.

### Tools installed (2026-11-02)

- Helm v4.3.1 and k3d v5.9.0 (default k3s v1.35.5-k3s1), both through winget.
- k3d came from winget and not a manual download, because winget offers the same pinned version.
