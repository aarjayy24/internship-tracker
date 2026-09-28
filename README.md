# Internship Tracker — Summer 2027

Watches ~55 company career sites directly (Google, Amazon, Microsoft, NVIDIA, OpenAI,
Anthropic, Databricks, xAI, …) plus the [SimplifyJobs Summer 2027 list](https://github.com/SimplifyJobs/Summer2027-Internships)
(Meta, Apple and thousands more). New DS / ML / AI / SDE internships trigger a phone push
(ntfy) and an email within ~10 minutes. Runs 24/7 on GitHub Actions.

**[→ All open matching roles](OPEN_ROLES.md)**

## What gets filtered
- Intern / co-op / student researcher roles only, Summer 2027 (other terms dropped)
- DS, ML, AI, SDE, data engineering, analytics, research engineering
- US locations; roles requiring US citizenship or clearance dropped
- PhD-only and BS-only roles dropped (toggle in `tracker/config.py`)
- Flags ⚠️: "no sponsorship" (usually still fine for CPT — verify), graduation windows that exclude Dec 2027

## Tuning
Everything lives in [`tracker/config.py`](tracker/config.py): companies, keywords, top-tier list,
PhD/BS toggles. Commit and push — the next run uses it.

Top-tier companies (`TIER1`) get urgent-priority pushes; everyone else gets normal pushes.
If more than 8 new roles land in one run you get a single summary push instead.

## Secrets (repo → Settings → Secrets and variables → Actions)
| Name | Value |
|---|---|
| `NTFY_TOPIC` | your private ntfy topic name |
| `GMAIL_ADDRESS` | the Gmail account that sends the alerts |
| `GMAIL_APP_PASSWORD` | a Gmail [app password](https://myaccount.google.com/apppasswords) (not your real password) |
| `EMAIL_TO` | where alerts go (optional; defaults to `GMAIL_ADDRESS`) |

## Local run
```bash
python3 -m tracker.main --dry-run      # fetch + print matches, send/save nothing
python3 -m unittest tests.test_filters
```
On a python.org install of Python on macOS, prefix with `SSL_CERT_FILE=/etc/ssl/cert.pem` if you see certificate errors.
