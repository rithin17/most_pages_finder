"""
generate_sample_log.py
-----------------------
Stage 0 (supporting utility): Synthetic dataset generator.

Since a real multi-gigabyte web server log (e.g. the NASA-HTTP July 1995
dataset referenced in the project slides) isn't available in this
environment, this script generates a realistic *synthetic* access log in
Common Log Format (CLF) that mimics that dataset's structure:

    host - - [dd/Mon/yyyy:HH:MM:SS -0400] "METHOD /path HTTP/1.0" status bytes

It deliberately injects the kinds of "noise" a real log contains, so the
Data Cleaning stage in pipeline.py has real work to do:
  - bot / crawler traffic
  - duplicate hits (same client re-requesting the same resource instantly)
  - non-2xx responses (404s, 304 not-modified, 500s)
  - a handful of malformed lines
"""

import random
from datetime import datetime, timedelta

# A realistic pool of "popular" pages so a clear ranking emerges,
# plus a long tail of rarely-visited pages.
POPULAR_PAGES = [
    "/shuttle/countdown/",
    "/history/apollo/",
    "/shuttle/missions/sts-71/",
    "/images/ksclogo-medium.gif",
    "/shuttle/countdown/liftoff.html",
    "/shuttle/missions/sts-73/",
]

LONG_TAIL_PAGES = [
    "/history/apollo/apollo-13/apollo-13.html",
    "/shuttle/missions/sts-69/",
    "/shuttle/technology/sts-newsref/stsref-toc.html",
    "/facilities/kscmap.html",
    "/history/mercury/mercury.html",
    "/history/gemini/gemini.html",
    "/images/launch-logo.gif",
    "/shuttle/missions/missions.html",
    "/software/winvn/winvn.html",
    "/robots.txt",
    "/history/apollo/apollo-11/apollo-11.html",
    "/shuttle/countdown/video/livevideo.gif",
]

METHODS = ["GET", "GET", "GET", "GET", "POST", "HEAD"]

# Regular human/browser client hosts
CLIENT_HOSTS = [
    "199.72.81.55", "unicomp6.unicomp.net", "199.120.110.21",
    "burger.letters.com", "205.212.115.106", "d104.aa.net",
    "129.94.144.152", "ppp851.pm2.abo.wau.nl", "163.206.104.34",
    "www-b2.proxy.aol.com", "kgtyk4.kj.yamagata-u.ac.jp", "grimnet23.idirect.com",
]

# Hosts that identify themselves (by name) as bots/crawlers -> filtered out
# during Data Cleaning.
BOT_HOSTS = [
    "crawler1.googlebot.com", "spider2.altavista.digital.com",
    "webbot-scanner.infoseek.com", "bot-indexer.lycos.com",
]

STATUS_WEIGHTS = [(200, 0.86), (304, 0.06), (404, 0.06), (500, 0.02)]


def _weighted_status():
    r = random.random()
    cum = 0.0
    for status, weight in STATUS_WEIGHTS:
        cum += weight
        if r <= cum:
            return status
    return 200


def _random_timestamp(base, offset_seconds):
    ts = base + timedelta(seconds=offset_seconds)
    return ts.strftime("%d/%b/%Y:%H:%M:%S -0400")


def generate_log(path, n_lines=5000, seed=42):
    random.seed(seed)
    base = datetime(1995, 7, 1, 0, 0, 0)
    lines = []

    for i in range(n_lines):
        # 5% pure bot traffic
        if random.random() < 0.05:
            host = random.choice(BOT_HOSTS)
            page = random.choice(POPULAR_PAGES + LONG_TAIL_PAGES)
        else:
            host = random.choice(CLIENT_HOSTS)
            # 70% of real traffic goes to the "popular" pages -> Zipf-ish skew
            page = random.choice(POPULAR_PAGES) if random.random() < 0.7 \
                else random.choice(LONG_TAIL_PAGES)

        method = random.choice(METHODS)
        status = _weighted_status()
        size = random.choice([0, 3985, 4085, 6245, 1024, 8192, "-"])
        ts = _random_timestamp(base, i * random.randint(1, 4))

        line = f'{host} - - [{ts}] "{method} {page} HTTP/1.0" {status} {size}'
        lines.append(line)

        # Occasionally duplicate the exact same hit (double-click / retry)
        if random.random() < 0.03:
            lines.append(line)

    # Sprinkle in a few malformed lines to test the parser's robustness
    for _ in range(15):
        pos = random.randint(0, len(lines) - 1)
        lines.insert(pos, "MALFORMED ENTRY :: unparsable garbage %%%")

    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")

    print(f"Generated {len(lines)} log lines -> {path}")


if __name__ == "__main__":
    generate_log("data/sample_access.log", n_lines=5000)
