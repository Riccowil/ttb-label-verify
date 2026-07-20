# ADR-002: Hosted vision API for prototype, swappable provider interface

## Context
TTB's network blocks many outbound ML endpoints (per IT interview);
production would require FedRAMP-authorized or self-hosted inference.

## Decision
Prototype uses a hosted Claude vision endpoint behind a single
extraction.py interface; model/provider is config, not code.

## Consequences
Fast prototype delivery and sub-5s latency; production migration is an
adapter swap, not a rewrite.

Trade-off: the deployed prototype would not run inside TTB's firewall
as-is — documented, not hidden.
