# Using the PJM Data Miner 2 API for Hourly Load

This guide explains how the PJM Data Miner 2 API works, how this repo's
[`fetch_pjm.py`](../fetch_pjm.py) talks to it, and how to construct calls for the
**hourly load** feeds covering **every available field**.

It is grounded in two sources:

- This repository — [`README.md`](../README.md) (CLI usage, feed catalog, zone
  values), [`CONTEXT.md`](../CONTEXT.md) (the *Subscription Key* term),
  [`ADR-0001`](adr/0001-personal-subscription-key-via-env.md) (auth decision),
  and the source files [`fetch_pjm.py`](../fetch_pjm.py),
  [`get_pjm_url.py`](../get_pjm_url.py),
  [`get_subscription_headers.py`](../get_subscription_headers.py).
- The official **PJM Data Miner API Guide** (©2026), which is the authoritative
  source for field names, allowed filter values, and query parameters:
  <https://www.pjm.com/-/media/DotCom/etools/data-miner-2/data-miner-2-api-guide.ashx>.
  Feed metadata and field lists are also browsable at <https://apiportal.pjm.com>.

> **New here?** Read [`CONTEXT.md`](../CONTEXT.md) first for the definition of
> *Subscription Key*, then skim the feed catalog in [`README.md`](../README.md).

---

## 1. API fundamentals

### Base URL and feed discovery

All requests go to:

```
https://api.pjm.com/api/v1/
```

The root URL returns a catalog of every feed. Each catalog entry has a `name`
(the short **URL key**, e.g. `hrl_load_metered`), a `displayName`, a
`description`, and a `links[].href` pointing at the feed's own endpoint. This
repo discovers feed URLs by matching the URL key against that catalog — see
[`get_pjm_url.py`](../get_pjm_url.py) (`get_pjm_links`, `get_pjm_url`). The full
catalog is also rendered as a table in [`README.md`](../README.md#available-url-keys),
or list it yourself with `python fetch_pjm.py --list`.

A resolved feed endpoint looks like:

```
https://api.pjm.com/api/v1/hrl_load_metered
```

Each feed actually exposes **two** endpoints:

| Endpoint | Purpose |
|---|---|
| `/<feed>/metadata` | Feed definition and publication frequency. Takes **no** input attributes. |
| `/<feed>` (the *search* endpoint) | The data itself. Accepts the filter / pagination / field parameters described below. |

### Authentication — the Subscription Key

Every request must carry a personal **Subscription Key** (see
[`CONTEXT.md`](../CONTEXT.md)). Register at the
[PJM developer portal](https://apiportal.pjm.com), then send the key on the
`Ocp-Apim-Subscription-Key` HTTP header:

```
Ocp-Apim-Subscription-Key: <your key>
```

This repo reads the key from the `PJM_SUBSCRIPTION_KEY` environment variable
(loaded from `.env`) and builds that header in
[`get_subscription_headers.py`](../get_subscription_headers.py). The decision to
use a per-user key on a header — rather than the old shared public key — is
recorded in [`ADR-0001`](adr/0001-personal-subscription-key-via-env.md). PJM also
accepts the key as a `subscription-key=<key>` **query parameter**, but this repo
standardizes on the header, and you should too.

> Production and test environments have **different** keys; they are not
> interchangeable.

### Response shape and pagination

A search response is JSON with three top-level keys:

```jsonc
{
  "totalRows": 528,                       // total matching rows across all pages
  "items": [ { /* one row */ }, ... ],    // this page's rows
  "links": [
    { "rel": "next", "href": "https://api.pjm.com/api/v1/hrl_load_metered?startRow=51&..." },
    { "rel": "first", "href": "..." }
    // self / prev / last as applicable
  ]
}
```

To retrieve a full result set, follow the link whose `rel` is `next` until no
`next` link remains. [`fetch_pjm.py`](../fetch_pjm.py) does exactly this in
`fetch_paginated_data` — it reads `totalRows`, accumulates `items`, and walks
`next` links, so you normally don't have to think about page size at all.

If you set **`download=true`** (see below), the shape changes: only the rows are
returned (no `links`, no echoed search criteria), the total count moves to the
`X-TotalRows` response header, and `rowCount` becomes optional.

---

## 2. The hourly load feeds

PJM publishes three hourly load feeds. They share the same query mechanics but
have **different field sets** and represent different data-quality stages:

| URL key | Display name | What it is |
|---|---|---|
| [`hrl_load_metered`](../README.md#available-url-keys) | Hourly Load: Metered | Best-quality metered MW‑hour net energy for load, by zone/load area. Carries a *Company Verified* flag. Adjustments can occur up to **90 days** after the actual date. |
| `hrl_load_estimated` | Hourly Load: Estimated | Estimated integrated hourly loads from meter data — revenue-quality but not yet verified by the EDCs. |
| `hrl_load_prelim` | Hourly Load: Preliminary | Preliminary loads computed daily from raw telemetry; approximate, informational only. |

The rest of this guide uses **`hrl_load_metered`** as the worked example because
it is the richest feed (and the one with a [sample CSV](../samples/hrl_load_metered-20191215121616.csv)
in this repo), then lists the field differences for the other two.

---

## 3. Field reference — *all possible fields*

Field names with the `_ept` suffix are **Eastern Prevailing Time** (EST or EDT as
appropriate); `_utc` fields are **UTC**. The `_beginning_` notation means the
timestamp marks the **start** of the hourly interval. All value filters below are
**partial, case-insensitive** matches.

### `hrl_load_metered` — 8 fields

| Field | Filterable? | Description | Allowed filter values |
|---|---|---|---|
| `datetime_beginning_utc` | range | Start of the hour, UTC | date-time (see §4) |
| `datetime_beginning_ept` | range | Start of the hour, Eastern Prevailing Time | date-time (see §4) |
| `nerc_region` | yes | NERC region | `OTHER`, `RFC`, `RTO`, `SERC` |
| `mkt_region` | yes | Market region | `MIDATL`, `OTHER`, `RTO`, `SOUTH`, `WEST` |
| `zone` | yes | Transmission zone | `AE`, `AEP`, `AP`, `ATSI`, `BC`, `CE`, `DAY`, `DEOK`, `DOM`, `DPL`, `DUQ`, `EKPC`, `JC`, `ME`, `OTHER`, `PE`, `PEP`, `PL`, `PN`, `PS`, `RECO`, `RTO` |
| `load_area` | yes | Load area | `AE`, `AECO`, `AEPAPT`, `AEPIMP`, `AEPKPT`, `AEPOPT`, `AP`, `BC`, `CE`, `DAY`, `DEOK`, `DOM`, `DPLCO`, `DUQ`, `EASTON`, `EKPC`, `JC`, `ME`, `OE`, `PAPWR`, `PE`, `PEPCO`, `PLCO`, `PN`, `PS`, `RECO`, `RTO`, `SMECO`, `UGI` |
| `mw` | — | MW‑hour net energy for load consumed in the territory | numeric |
| `is_verified` | yes | *Company Verified* flag — has the EDC verified the value? | `TRUE`, `FALSE` |

> The `zone` list above matches the values documented in
> [`README.md`](../README.md#available-zone-values-for-hrl_load_metered), and the
> column layout matches the [sample CSV](../samples/hrl_load_metered-20191215121616.csv)
> header: `datetime_beginning_utc, datetime_beginning_ept, nerc_region,
> mkt_region, zone, load_area, mw, is_verified`.
>
> Control Area / NERC Region / Market Region / Zone / Load Area mapping reference
> (informational, not maintained):
> <https://pjm.com/-/media/etools/data-miner-2/hourly-loads-area-mapping.ashx?la=en>

### `hrl_load_estimated` — 6 fields

| Field | Filterable? | Allowed filter values |
|---|---|---|
| `datetime_beginning_utc` | range | date-time |
| `datetime_beginning_ept` | range | date-time |
| `datetime_ending_utc` | range | date-time |
| `datetime_ending_ept` | range | date-time |
| `load_area` | yes | `AEP`, `COMED`, `DAYTON`, `DEOK`, `DOM`, `DUQ`, `EKPC`, `FE`, `PJME`, `PJMW` |
| `estimated_load_hourly` | — | estimated hourly load (MW) |

### `hrl_load_prelim` — 6 fields

| Field | Filterable? | Allowed filter values |
|---|---|---|
| `datetime_beginning_utc` | range | date-time |
| `datetime_beginning_ept` | range | date-time |
| `datetime_ending_utc` | range | date-time |
| `datetime_ending_ept` | range | date-time |
| `load_area` | yes | `AEP`, `AP`, `ATSI`, `DAY`, `DEOK`, `DOM`, `DUQ`, `EKPC`, `MIDATL`, `NI` |
| `prelim_load_avg_hourly` | — | preliminary average hourly load (MW) |

---

## 4. Constructing calls

A search call is the feed URL plus query parameters. There are two kinds:
**generic** parameters (work on every feed) and **feed-specific** field filters
(the columns in §3).

### Generic query parameters

| Parameter | Meaning |
|---|---|
| `rowCount` | Max rows per page. **Max 50,000.** Required if *any* other parameter is specified — *unless* `download=true`. |
| `startRow` | 1-based index of the first row to return (`1` = very first row). Required if any other parameter is specified. |
| `sort` | Field name to sort on. |
| `order` | `Asc` or `Desc` (default `Asc`). |
| `fields` | CSV list of field names to return — use this to project a subset (or to be explicit about *all* fields). |
| `download` | `true` → return only rows, no links/criteria; total moves to the `X-TotalRows` header; `rowCount` becomes optional. |
| `format` | Output format, e.g. `csv`. |

> **Important pagination rule.** The guide states that `rowCount` *and*
> `startRow` are **required whenever any other parameter is present**. A bare
> date-range query therefore technically needs them too. [`fetch_pjm.py`](../fetch_pjm.py)
> does **not** add them automatically — it relies on the server's default page
> plus `next`-link following. If a filtered query is rejected, add them
> explicitly (via `-F`, see §5): `-F rowCount=50000 -F startRow=1`. Setting
> `-F download=true` is the other escape hatch (makes `rowCount` optional).

### Date / time filtering

Date fields accept either a **named range** or an **explicit range**.

**Named values** (case-sensitive): `Today`, `Yesterday`, `CurrentWeek`,
`LastWeek`, `NextWeek`, `CurrentMonth`, `LastMonth`, `NextMonth`, `CurrentYear`,
`LastYear`, `NextYear`.

**Explicit range** uses the literal word `to` between two timestamps on the same
field:

```
datetime_beginning_ept=9/1/2016 00:00 to 10/31/2016 23:00
```

A few notes on the explicit form:

- PJM accepts a variety of date formats (`M/D/YYYY HH:MM`, `D-MM-YYYY HH:MM`,
  etc.); be consistent and prefer 24-hour times.
- This repo always filters on **`datetime_beginning_ept`** and joins the two ends
  with `" to "` — see `build_params` in [`fetch_pjm.py`](../fetch_pjm.py). If you
  give it a date with no time, it appends ` 00:00` to the start and ` 23:59` to
  the end (`_add_time`), using the space separator PJM expects.
- You can also leave one side open (`to <end>` or `<start> to`).

### Field-value filtering

Add `field=value` for any filterable column in §3. Matches are partial and
case-insensitive, e.g. `zone=AEP`, `is_verified=TRUE`, `nerc_region=RFC`. Combine
freely with the date range and generic parameters.

---

## 5. Using the CLI (`fetch_pjm.py`)

[`fetch_pjm.py`](../fetch_pjm.py) wraps all of the above. CLI flags map onto API
parameters like this:

| CLI flag | API effect |
|---|---|
| `-u, --url <key>` | Resolves the URL key to its feed endpoint (via [`get_pjm_url.py`](../get_pjm_url.py)). |
| `-s, --start` / `-e, --end` | Build `datetime_beginning_ept=<start> to <end>`. |
| `-F, --filter KEY=VALUE` | Pass **any** query parameter through verbatim — field filters *and* generic params (`fields`, `rowCount`, `sort`, …). Repeatable. |
| `-f, --format` | Output encoding: `csv` (default), `json`, `xls`, `stdout`, `raw`. |
| `-o, --output` | Output filename (otherwise auto-named `<key>-<timestamp>.<format>`). |
| `-l, --list` | Print the full feed catalog. |

Because `-F` passes parameters straight onto the URL, it is how you reach **every**
API capability — not just the feed columns. Examples:

```shell
# All metered-load rows for January 2024 (auto-paginated), as CSV
python fetch_pjm.py -u hrl_load_metered --start "2024-01-01" --end "2024-01-31"

# One hour, one zone, verified values only
python fetch_pjm.py -u hrl_load_metered \
  --start "2024-01-01 00:00" --end "2024-01-01 00:00" \
  -F zone=AEP -F is_verified=TRUE

# Project a subset of columns and sort, explicit paging params
python fetch_pjm.py -u hrl_load_metered --start "2024-01-01" --end "2024-01-31" \
  -F "fields=datetime_beginning_ept,zone,load_area,mw,is_verified" \
  -F sort=datetime_beginning_ept -F order=Asc \
  -F rowCount=50000 -F startRow=1

# Estimated and preliminary feeds (different value field names)
python fetch_pjm.py -u hrl_load_estimated --start "2024-01-01" --end "2024-01-07" -F load_area=AEP
python fetch_pjm.py -u hrl_load_prelim   --start "2024-01-01" --end "2024-01-07" -F load_area=MIDATL
```

See [`README.md`](../README.md#run-the-data-collection-script-examples) for more
CLI examples and the available `hrl_load_metered` zone values.

---

## 6. Raw HTTP (without the CLI)

To pull **all fields** of metered hourly load for a date range, directly:

**curl** (header auth, per [`ADR-0001`](adr/0001-personal-subscription-key-via-env.md)):

```shell
curl --compressed \
  -H "Ocp-Apim-Subscription-Key: $PJM_SUBSCRIPTION_KEY" \
  "https://api.pjm.com/api/v1/hrl_load_metered?download=true&sort=datetime_beginning_ept&order=Asc&datetime_beginning_ept=1/1/2024 00:00 to 1/31/2024 23:00" \
  -o hrl_load_metered.json
```

**Python** (mirrors how [`fetch_pjm.py`](../fetch_pjm.py) does it — header from
`PJM_SUBSCRIPTION_KEY`, follow `next` links for full pagination):

```python
import os, requests

headers = {"Ocp-Apim-Subscription-Key": os.environ["PJM_SUBSCRIPTION_KEY"]}
url = "https://api.pjm.com/api/v1/hrl_load_metered"
params = {
    "datetime_beginning_ept": "1/1/2024 00:00 to 1/31/2024 23:00",
    "rowCount": 50000,
    "startRow": 1,
    "sort": "datetime_beginning_ept",
    "order": "Asc",
    # omit `fields` to return all 8 columns, or set it explicitly:
    # "fields": "datetime_beginning_utc,datetime_beginning_ept,nerc_region,mkt_region,zone,load_area,mw,is_verified",
}

rows, first = [], True
while url:
    resp = requests.get(url, headers=headers, params=params if first else None)
    resp.raise_for_status()
    body = resp.json()
    rows.extend(body["items"])
    url = next((l["href"] for l in body["links"] if l["rel"] == "next"), None)
    first = False

print(f"{len(rows)} rows")
```

---

## 7. Gotchas

- **`rowCount` + `startRow` are required with any other parameter** (see §4).
  Omitting them returns a 400 whose body reads `"Row count is missing"` (or the
  `startRow` equivalent). If a filtered request errors, add them
  (`-F rowCount=50000 -F startRow=1`) or set `download=true`.
- **Missing date error.** A search with filters but no date range returns:
  `"A datetime is missing. Please input values for datetime_beginning_ept or
  datetime_beginning_utc"`. Always supply a date range for these feeds.
- **Archived vs. standard data.** PJM moves older data to an archive with *less*
  query flexibility. A range that spans the archive boundary is rejected
  (`"Date range ... spans over archived and standard data"`). Split such queries
  at the boundary.
- **90-day adjustment window.** `hrl_load_metered` values can change up to 90 days
  after the operating day; re-pull recent data if you need final figures, and use
  `is_verified=TRUE` to filter to EDC-verified rows.
- **EPT vs UTC / DST.** `_ept` fields follow daylight saving; for monotonic,
  gap/overlap-free timestamps, key your warehouse on `datetime_beginning_utc`.
- **Partial, case-insensitive matches.** `zone=PE` also matches `PEP`. Use exact
  documented values to avoid surprises.
- **`mw` field name.** The metered feed's value column is `mw`; the estimated and
  preliminary feeds use `estimated_load_hourly` and `prelim_load_avg_hourly`
  respectively (§3).

---

## See also

- [`README.md`](../README.md) — install, CLI usage, full feed catalog, zone list.
- [`CONTEXT.md`](../CONTEXT.md) — *Subscription Key* and project vocabulary.
- [`ADR-0001`](adr/0001-personal-subscription-key-via-env.md) — why auth uses a
  per-user key on the `Ocp-Apim-Subscription-Key` header.
- Source: [`fetch_pjm.py`](../fetch_pjm.py),
  [`get_pjm_url.py`](../get_pjm_url.py),
  [`get_subscription_headers.py`](../get_subscription_headers.py).
- Sample output: [`samples/hrl_load_metered-…csv`](../samples/hrl_load_metered-20191215121616.csv).
- Official **PJM Data Miner API Guide**:
  <https://www.pjm.com/-/media/DotCom/etools/data-miner-2/data-miner-2-api-guide.ashx>
  · API portal: <https://apiportal.pjm.com>
