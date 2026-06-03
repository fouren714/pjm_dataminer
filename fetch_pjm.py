import argparse
import datetime
import json
import logging
import urllib.parse
import requests
import tablib
from get_pjm_url import get_pjm_list, get_pjm_url
from get_subscription_headers import get_subsription_headers
import coloredlogs

# Constants
VERSION = "1.0"
DEFAULT_OUTPUT_FORMAT = "csv"
OUTPUT_FORMATS = ["csv", "json", "xls", "stdout", "raw"]

# Initialize Logger
def setup_logger():
    logger = logging.getLogger("fetch_pjm")
    logger.setLevel(logging.DEBUG)
    coloredlogs.install()
    return logger

logger = setup_logger()

# Argument Parsing
def parse_arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", "-u", help="Set URL key for data extraction. e.g., solar_gen, pnode, etc.")
    parser.add_argument("--output", "-o", help="Set filename to output")
    parser.add_argument("--format", "-f", help="Set format for output", choices=OUTPUT_FORMATS, default=DEFAULT_OUTPUT_FORMAT)
    parser.add_argument("--list", "-l", help="Output list of all URLs", action="store_true")
    parser.add_argument("--start", "-s", help="Start of date range, e.g. '2024-01-01' or '2024-01-01 06:00'")
    parser.add_argument("--end", "-e", help="End of date range, e.g. '2024-01-31' or '2024-01-31 23:00'")
    parser.add_argument("--filter", "-F", action="append", metavar="KEY=VALUE",
                        help="Feed-specific filter, e.g. zone=AEP or is_verified=TRUE. Repeatable.")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser.parse_args()

args = parse_arguments()

# Functions
def get_header():
    headers = get_subsription_headers()
    logger.info("Fetched subscription header")
    return headers

def _add_time(date_str, default_time):
    if not date_str:
        return date_str
    # PJM's date parser wants a space between the date and time
    # (e.g. "2024-01-01 00:00"), not an ISO "T" separator. Append a default
    # time to a bare date, and normalize any "T" the caller passed to a space.
    # See docs/research.md "Date / time filtering".
    if "T" not in date_str and " " not in date_str:
        return f"{date_str} {default_time}"
    return date_str.replace("T", " ")

# Keys PJM uses to carry a human-readable error message in a JSON error body.
# APIM-level errors (bad/missing subscription key, throttling) use "message";
# Data Miner validation errors come back under "errors". See docs/research.md §7.
_ERROR_MESSAGE_KEYS = ("message", "Message", "error", "detail")

def _truncate(text, limit):
    if text and len(text) > limit:
        return f"{text[:limit]}… (truncated)"
    return text

def _extract_error_detail(response, limit=2000):
    # requests' HTTPError string only carries the status line ("400 Client Error:
    # Bad Request for url: ..."); the *reason* lives in the response body. PJM puts
    # it there as JSON ({"message": ...} or {"errors": [...]}) or occasionally plain
    # text. Surface that so a 400 explains itself. Returns None if there's nothing.
    if response is None:
        return None
    try:
        body = response.json()
    except ValueError:
        text = (response.text or "").strip()
        return _truncate(text, limit) or None

    if isinstance(body, dict):
        for key in _ERROR_MESSAGE_KEYS:
            value = body.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        errors = body.get("errors")
        if isinstance(errors, list):
            messages = []
            for item in errors:
                if isinstance(item, dict):
                    messages.append(item.get("error") or item.get("message") or json.dumps(item))
                else:
                    messages.append(str(item))
            joined = "; ".join(m for m in messages if m)
            if joined:
                return _truncate(joined, limit)
    # No recognized field — show the raw body rather than hiding it.
    return _truncate(json.dumps(body), limit)

def build_params(args):
    params = {}
    if args.start or args.end:
        start = _add_time(args.start, "00:00")
        end = _add_time(args.end, "23:59")
        if start and end:
            params["datetime_beginning_ept"] = f"{start} to {end}"
        elif start:
            params["datetime_beginning_ept"] = f"{start} to"
        else:
            params["datetime_beginning_ept"] = f"to {end}"
    if args.filter:
        for f in args.filter:
            key, _, value = f.partition("=")
            params[key.strip()] = value.strip()
    return params

def attach_params(url, params):
    if not params:
        return url
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{qs}"

def output_data_list():
    list = get_pjm_list()
    print("|url|display name and description|")
    print("|---|---|")
    for l in list:
        print(f"|{l['name']}|*{l['displayName']}* {l['description']}|")

def fetch_paginated_data(url, headers, params=None):
    items = []
    total_rows = None
    retrieved_rows = 0
    first_page = True

    while url:
        try:
            request_url = attach_params(url, params) if first_page else url
            response = requests.get(request_url, headers=headers)
            response.raise_for_status()
            data = response.json()

            if total_rows is None:
                total_rows = int(data['totalRows'])

            new_items = data['items']
            items.extend(new_items)
            retrieved_rows += len(new_items)
            logger.info(f"Retrieved {retrieved_rows}/{total_rows} rows")

            # Check for next page
            next_page = next((link['href'] for link in data['links'] if link['rel'] == 'next'), None)
            url = next_page
            first_page = False
        except requests.HTTPError as e:
            response = e.response
            status = response.status_code if response is not None else "unknown"
            detail = _extract_error_detail(response)
            logger.error(f"PJM API returned HTTP {status}: {detail}" if detail
                         else f"PJM API returned HTTP {status}: {e}")
            if status == 400:
                logger.error(
                    "A 400 means PJM rejected the request. Common causes: a missing "
                    "row count or start row — PJM requires rowCount and startRow "
                    "whenever any other parameter is sent (add -F rowCount=50000 "
                    "-F startRow=1, or -F download=true); no date range (add "
                    "--start/--end); or a range spanning PJM's archive boundary "
                    "(split it). See docs/research.md §4 and §7."
                )
            exit(1)
        except requests.RequestException as e:
            logger.error(f"Error fetching data: {e}")
            exit(1)

    return items

def generate_output_filename(url, format):
    return f"{url}-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{format}"

def save_data(data, output, format):
    with open(output, "w" if format != "xls" else "wb") as f:
        if format != "xls":
            f.write(data.export(format))
        else:
            f.write(data.export(format))

# Main Script Logic
if args.list:
    output_data_list()
    exit()

if not args.url:
    logger.error("URL not provided")
    exit(1)

url = get_pjm_url(args.url)
logger.info(f"Set URL to {url}")

headers = get_header()
params = build_params(args)
items = fetch_paginated_data(url, headers, params)

output = args.output if args.output else generate_output_filename(args.url, args.format)
logger.info(f"Writing {args.format} - {output}")

if args.format == "raw":
    print(items)
else:
    data = tablib.Dataset()
    if items:
        data.headers = items[0].keys()
        for item in items:
            data.append(item.values())

    if args.format == "stdout":
        print(data.csv)
    elif args.format in OUTPUT_FORMATS:
        save_data(data, output, args.format)
    else:
        logger.error("Invalid output format")
        exit(1)

logger.info("Complete")
