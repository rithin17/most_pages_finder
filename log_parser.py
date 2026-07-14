"""
log_parser.py
--------------
Stage 2: Data Preprocessing.

Parses a single Common Log Format (CLF) access-log line into its
structured fields using a regular expression:

    host - - [timestamp] "METHOD url PROTOCOL" status size

Returns None for lines that don't match (malformed entries), so callers
can simply discard them.
"""

import re

LOG_PATTERN = re.compile(
    r'^(?P<host>\S+) \S+ \S+ '
    r'\[(?P<timestamp>[^\]]+)\] '
    r'"(?P<method>[A-Z]+) (?P<url>\S+)(?: \S+)?" '
    r'(?P<status>\d{3}) (?P<size>\S+)$'
)

BOT_KEYWORDS = ("bot", "crawler", "spider")


def parse_line(line: str):
    """Parse one raw log line into a dict of fields, or None if malformed."""
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    fields = match.groupdict()
    fields["status"] = int(fields["status"])
    fields["size"] = 0 if fields["size"] == "-" else int(fields["size"])
    fields["is_bot"] = any(kw in fields["host"].lower() for kw in BOT_KEYWORDS)
    return fields


def parse_log_file(path: str):
    """
    Parse every line in a log file.

    Returns:
        parsed (list[dict]): successfully parsed records
        n_malformed (int): count of lines that failed to parse
    """
    parsed = []
    n_malformed = 0

    with open(path, "r") as f:
        for line in f:
            if not line.strip():
                continue
            record = parse_line(line)
            if record is None:
                n_malformed += 1
            else:
                parsed.append(record)

    return parsed, n_malformed
