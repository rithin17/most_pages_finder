# Most Visited Pages Finder

Identifying and Ranking Frequently Accessed Webpages from Web Server Access Logs.

A data analytics project under **Web Usage Mining** — it parses raw web
server access logs, cleans out noise (bots, duplicates, error responses),
counts how often each page is requested, and reports the Top-N most
visited pages as a CSV table and a bar chart.

Guided by: Binju Saju | CSE-DS | 2024-28
Group: Amruth Krishnan J, Chrison Roy, Rithin Ratheesh

## Pipeline

This implements the six-stage methodology from the project proposal:

| # | Stage | Where |
|---|-------|-------|
| 1 | Data Collection | `data/sample_access.log` (or your own log file) |
| 2 | Data Preprocessing | `src/log_parser.py` — regex extraction of host, timestamp, method, URL, status, size |
| 3 | Data Cleaning | `src/pipeline.py::clean_records` — drops bot/crawler traffic, duplicate hits, non-2xx responses |
| 4 | Structured Storage | `src/pipeline.py::to_dataframe` — loads cleaned records into a Pandas DataFrame |
| 5 | Frequency Analysis | `src/pipeline.py::frequency_analysis` — `collections.Counter` over requested URLs |
| 6 | Ranking & Reporting | `src/pipeline.py::rank_and_report` — sorts by visit count, saves `output/top_pages.csv` and `output/top_pages_chart.png` |

## Project structure

```
most_visited_pages_finder/
├── data/
│   └── sample_access.log        # synthetic NASA-style CLF access log
├── output/
│   ├── top_pages.csv            # ranked report
│   └── top_pages_chart.png      # bar chart visualisation
├── src/
│   ├── generate_sample_log.py   # synthetic dataset generator
│   ├── log_parser.py            # Stage 2: regex log-line parser
│   └── pipeline.py              # Stages 3-6: clean, store, analyse, report
├── requirements.txt
└── README.md
```

## Setup

```bash
pip install -r requirements.txt
```

## Usage

1. (Optional) Generate a fresh synthetic dataset — or drop in a real
   Apache/Nginx access log at `data/sample_access.log`:

   ```bash
   python src/generate_sample_log.py
   ```

2. Run the pipeline:

   ```bash
   python src/pipeline.py --log data/sample_access.log --top 10 --output output
   ```

   Options:
   - `--log`     path to the access log file (default: `data/sample_access.log`)
   - `--top`     how many top pages to report (default: `10`)
   - `--output`  output directory for the CSV and chart (default: `output`)

The console prints progress through all six stages, then the final
ranked table. Results are also saved to `output/top_pages.csv` and
`output/top_pages_chart.png`.

## Log format

Records follow the Common Log Format (CLF), matching the NASA-HTTP
July 1995 benchmark dataset referenced in the project's related work:

```
199.72.81.55 - - [01/Jul/1995:00:00:01 -0400] "GET /history/apollo/ HTTP/1.0" 200 6245
```

## Language & Tools

- **Python 3** — core programming language for the entire pipeline
- **Pandas** — loading, structuring, and aggregating log data
- **re (Regex)** — parsing raw log lines into structured fields
- **Matplotlib / Seaborn** — visualising top pages as bar charts
- **collections.Counter** — fast frequency counting of page URLs

## Using a real dataset

To point the pipeline at the real NASA-HTTP log (or any other Apache/Nginx
access log in CLF), just replace `data/sample_access.log` with the real
file and re-run `src/pipeline.py --log <path>`. No code changes are
required as long as the log follows the standard CLF layout.
