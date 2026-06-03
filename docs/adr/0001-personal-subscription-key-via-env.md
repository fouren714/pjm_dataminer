# ADR 0001: Use personal PJM subscription key via environment variable

**Status:** Accepted  
**Date:** 2026-06-02

## Context

The original implementation fetched a public subscription key from `http://dataminer2.pjm.com/config/settings.json` at runtime. This key is shared across all anonymous users of the public portal — it is undocumented, could rotate without notice, and is not rate-limited per user.

PJM's developer portal issues personal `Ocp-Apim-Subscription-Key` credentials tied to individual accounts.

## Decision

Replace the dynamic key fetch with a user-supplied key read from the `PJM_SUBSCRIPTION_KEY` environment variable, loaded from a `.env` file via `python-dotenv`. If the variable is absent, the application raises a `RuntimeError` immediately.

## Consequences

- Users must register at the PJM developer portal and configure their own key before running the tool.
- The application fails fast with a clear error if the key is missing, rather than silently using a shared credential.
- The public key fetch and its `requests` call in `get_subscription_headers.py` are removed entirely — no fallback.
