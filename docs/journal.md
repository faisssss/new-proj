# Project journal

Decisions, mistakes and what changed.

## Week 1

### Laptop limits (2026-11-02)

- Docker can use 7.6 GB of memory (8,153,624,576 bytes) and 16 CPU threads.
- With the 1.5 GB of free memory the memory check requires, the full setup has about 6.1 GB.

### Tools installed (2026-11-02)

- Helm v4.3.1 and k3d v5.9.0 (default k3s v1.35.5-k3s1), both through winget.
- k3d came from winget and not a manual download, because winget offers the same pinned version.

### What metrics showed (2026-11-03)

- Deleting a pod doesn't raise the restart count, because the replacement is a new pod with 0 restarts. The restart metric alone would miss that failure.
- Pod names change when a pod is replaced, so the model has to work with service names, not pod names.
- Services have very different normal levels (`adservice` about 198 MB of memory, `checkoutservice` about 17 MB), so each one has to be compared with its own healthy baseline.
- Deleting the `currencyservice` pod showed up clearly on the CPU graph: the replacement pod spiked to about 5% of a core while starting, and `frontend` dipped at the same time.

### What traces showed (2026-11-04)

- 7 of the 10 services send their own spans. `adservice`, `cartservice` and `shippingservice` don't at this version.
- Decision: measure those three from the client spans of `frontend` and `checkoutservice`. Confirmed in Prometheus with 8 caller-side rows covering all three. The trade-off is that these numbers include network delay, and show nothing about what happens inside those services.
- Trouble travels up to the caller, not sideways. A slow `GetQuote` wouldn't slow down `Charge`, but it would slow down `checkoutservice`, which calls both.
- In one traced checkout, `PaymentService/Charge` was the slowest call from `checkoutservice`, at 1.7 ms of the 12.4 ms total.
