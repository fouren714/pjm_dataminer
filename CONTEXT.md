# PJM Data Miner — Ubiquitous Language

## Subscription Key

A personal API credential issued by PJM's developer portal to an individual user. Sent on every request to PJM's Data Miner API as the `Ocp-Apim-Subscription-Key` HTTP header. Each user supplies their own key via the `PJM_SUBSCRIPTION_KEY` environment variable.

Not to be confused with the public key formerly fetched from `dataminer2.pjm.com/config/settings.json`, which was shared and uncontrolled.
