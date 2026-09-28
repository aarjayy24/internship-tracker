"""Poll every source, alert on new matching internships, keep state in data/state.json.

Usage:
  python -m tracker.main            # normal poll (run every 10 min by GitHub Actions)
  python -m tracker.main --digest   # daily summary email
  python -m tracker.main --dry-run  # fetch + filter, print, send nothing, save nothing
"""
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from . import filters, notify, sources

ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "data" / "state.json"
ROLES_MD = ROOT / "OPEN_ROLES.md"
FAIL_ALERT_AFTER = 12        # consecutive failed polls (~2h) before warning you
FORGET_AFTER_DAYS = 120
MAX_DETAILS_PER_RUN = 250    # detail-page lookups (for deadlines) per run; the rest wait for the next run
RECHECK_DEADLINE_DAYS = 7

today = datetime.now(timezone.utc).strftime("%Y-%m-%d")


def key(company, title):
    return company.lower() + "|" + re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def roles_link():
    repo = os.environ.get("GITHUB_REPOSITORY")
    return f"https://github.com/{repo}/blob/main/OPEN_ROLES.md" if repo else "OPEN_ROLES.md"


def load_state():
    if STATE.exists():
        return json.loads(STATE.read_text())
    return {"bootstrapped": False, "jobs": {}, "health": {}}


def fetch_all():
    results, failed = {}, {}
    def run(item):
        name, fn = item
        try:
            return name, fn(), None
        except Exception as e:
            return name, None, f"{type(e).__name__}: {e}"
    with ThreadPoolExecutor(max_workers=16) as ex:
        for name, jobs, err in ex.map(run, sources.all_fetchers()):
            if err:
                failed[name] = err
            else:
                results[name] = jobs
    return results, failed


def poll(dry_run=False):
    state = load_state()
    jobs_state = state["jobs"]
    results, failed = fetch_all()
    total = sum(len(v) for v in results.values())
    print(f"fetched {total} postings from {len(results)} sources; {len(failed)} failed")
    for name, err in failed.items():
        print(f"  FAILED {name}: {err[:200]}")

    matched = []  # (fetcher_name, job, flags)
    for name, jobs in results.items():
        for j in jobs:
            keep, flags = filters.evaluate(j)
            if keep:
                matched.append((name, j, flags))
    print(f"{len(matched)} postings match your filters")
    enrich_deadlines(matched, jobs_state)
    if dry_run:
        for name, j, flags in sorted(matched, key=lambda m: (not notify.is_tier1(m[1].company), m[1].company)):
            dl = j.deadline or ("rolling" if j.rolling else "")
            print(f"  {j.company:18} | {j.title[:70]:70} | {dl:10} | {', '.join(j.locations)[:40]} {flags or ''}")
        return

    # Keys of postings that were already known and are still open: a new posting with
    # the same company+title is just another location/team copy, not worth an alert.
    open_known_keys = {key(j.company, j.title) for _, j, _ in matched if j.uid in jobs_state}
    all_known_keys = {v["key"] for v in jobs_state.values()}
    new_rows, alerted_keys = [], set()
    for name, j, flags in matched:
        k = key(j.company, j.title)
        rec = jobs_state.get(j.uid)
        dl = {"deadline": j.deadline, "rolling": j.rolling, "checked": today} if j.detailed else {}
        if rec:
            rec.update(last_seen=today, flags=flags, **dl)
            continue
        jobs_state[j.uid] = {"key": k, "src": name, "company": j.company, "title": j.title, "url": j.url,
                             "locations": j.locations, "flags": flags, "first_seen": today,
                             "first_seen_ts": time.time(), "posted_ts": j.posted_ts, "last_seen": today, **dl}
        if k in alerted_keys or k in open_known_keys:
            continue
        if k in all_known_keys and j.source == "simplify":
            continue   # already reported by a direct source
        alerted_keys.add(k)
        new_rows.append({**jobs_state[j.uid], "repost": k in all_known_keys})

    # Health tracking: warn once if a source keeps failing.
    for name in results:
        state["health"].pop(name, None)
    for name, err in failed.items():
        n = state["health"].get(name, 0) + 1
        state["health"][name] = n
        if n == FAIL_ALERT_AFTER:
            notify.push("⚠️ Tracker source failing", f"{name} has failed {n} times in a row: {err[:150]}",
                        priority=3, tags=["warning"])

    # Forget postings long gone.
    cutoff = datetime.now(timezone.utc).timestamp() - FORGET_AFTER_DAYS * 86400
    for uid in [u for u, v in jobs_state.items() if v.get("first_seen_ts", 0) < cutoff and v["last_seen"] != today]:
        del jobs_state[uid]

    open_jobs = [v for v in jobs_state.values()
                 if v["last_seen"] == today or (v["src"] in failed and _days_ago(v["last_seen"]) <= 2)]
    write_roles_md(open_jobs)

    if not state["bootstrapped"]:
        state["bootstrapped"] = True
        top = [v for v in open_jobs if notify.is_tier1(v["company"])]
        notify.push("✅ Internship tracker is live",
                    f"{len(open_jobs)} matching roles open right now ({len(top)} at top companies). "
                    + ("Check your email for the list." if notify.email_enabled() else "Tap to see the list."),
                    click=roles_link(), priority=4, tags=["rocket"])
        notify.email(f"✅ Tracker live — {len(open_jobs)} open matching internships",
                     f"<p>From now on you'll get a push + email within ~10 min of a new posting.</p>"
                     f"<h3>⭐ Top companies ({len(top)})</h3>{notify.jobs_table(sorted(top, key=lambda v: v['company']))}"
                     f"<p>Full list of all {len(open_jobs)} open roles: <a href=\"{roles_link()}\">OPEN_ROLES.md</a></p>")
    elif new_rows:
        print(f"{len(new_rows)} new → alerting")
        notify.announce_new(new_rows, roles_link())

    STATE.parent.mkdir(exist_ok=True)
    STATE.write_text(json.dumps(state, indent=0, sort_keys=True))


def enrich_deadlines(matched, jobs_state):
    """Fill job.deadline / job.rolling: reuse what state already knows, fetch detail
    pages for the rest (new postings first, then top companies), up to a per-run budget."""
    todo = []
    for _, j, _ in matched:
        rec = jobs_state.get(j.uid) or {}
        if j.detailed:
            continue
        if rec.get("checked") and _days_ago(rec["checked"]) < RECHECK_DEADLINE_DAYS:
            j.deadline, j.rolling = rec.get("deadline"), rec.get("rolling", False)
        else:
            todo.append(j)
    todo.sort(key=lambda j: (j.uid in jobs_state, not notify.is_tier1(j.company)))
    def fetch(j):
        try:
            sources.fetch_details(j)
        except Exception as e:
            print(f"  detail lookup failed for {j.url[:80]}: {type(e).__name__}")
    with ThreadPoolExecutor(max_workers=12) as ex:
        list(ex.map(fetch, todo[:MAX_DETAILS_PER_RUN]))
    print(f"deadline lookups: {min(len(todo), MAX_DETAILS_PER_RUN)} done, {max(0, len(todo) - MAX_DETAILS_PER_RUN)} queued")


def apply_by(v, md=True):
    d = v.get("deadline")
    if d:
        n = -_days_ago(d)
        label = datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d")
        if n < 0:   # stated date passed but the posting is still up
            return f"~~{label}~~ passed, still listed" if md else f"{label} (passed, still listed)"
        txt = f"{label} ({'today' if n == 0 else f'{n}d'})"
        return f"**{txt}**" if md and n <= 7 else txt
    return "rolling" if v.get("rolling") else "—"


def digest():
    state = load_state()
    recent = [v for v in state["jobs"].values() if time.time() - v.get("first_seen_ts", 0) < 86400]
    open_now = [v for v in state["jobs"].values() if _days_ago(v["last_seen"]) <= 1]
    recent.sort(key=lambda v: (not notify.is_tier1(v["company"]), v["company"].lower()))
    body = (f"<p>{len(recent)} new matching roles in the last 24h · {len(open_now)} open in total.</p>"
            + (notify.jobs_table(recent) if recent else "<p>No new roles today.</p>")
            + f"<p><a href=\"{roles_link()}\">All open roles</a></p>")
    problems = {k: v for k, v in state["health"].items() if v >= 3}
    if problems:
        body += "<p>⚠️ Sources currently failing: " + ", ".join(problems) + "</p>"
    closing = sorted((v for v in open_now if v.get("deadline") and 0 <= -_days_ago(v["deadline"]) <= 7),
                     key=lambda v: v["deadline"])
    if closing:
        body += "<h3>⏰ Deadlines in the next 7 days</h3>" + notify.jobs_table(closing)
    notify.email(f"📋 Daily internship digest — {len(recent)} new", body)
    if not notify.email_enabled():
        top = sorted({v["company"] for v in recent if notify.is_tier1(v["company"])})
        soon = "; ".join(f"{v['company']} {apply_by(v, md=False)}" for v in closing[:4])
        notify.push(f"📋 Daily digest: {len(recent)} new roles in 24h",
                    f"{len(open_now)} open in total." + (f" Top companies: {', '.join(top)}." if top else "")
                    + (f"\n⏰ Closing this week: {soon}" if closing else ""),
                    click=roles_link(), priority=2, tags=["clipboard"])


def write_roles_md(open_jobs):
    def rows(js):
        js = sorted(js, key=lambda v: (v["first_seen"], v.get("posted_ts") or 0), reverse=True)
        out = ["| Company | Role | Location | Apply by | Found | Notes |", "|---|---|---|---|---|---|"]
        for v in js:
            loc = ", ".join(l for l in v["locations"] if l)[:60].replace("|", "/")
            title = v["title"].replace("|", "/")
            out.append(f"| {v['company']} | [{title}]({v['url']}) | {loc} | {apply_by(v)} | {v['first_seen']} | "
                       f"{'⚠️ ' + '; '.join(v['flags']) if v['flags'] else ''} |")
        return "\n".join(out)
    top = [v for v in open_jobs if notify.is_tier1(v["company"])]
    rest = [v for v in open_jobs if not notify.is_tier1(v["company"])]
    closing = sorted((v for v in open_jobs if v.get("deadline") and 0 <= -_days_ago(v["deadline"]) <= 14),
                     key=lambda v: v["deadline"])
    n_dated = sum(1 for v in open_jobs if v.get("deadline"))
    n_rolling = sum(1 for v in open_jobs if v.get("rolling"))
    closing_md = rows_ordered(closing) if closing else "_No stated deadlines in the next 14 days._"
    ROLES_MD.write_text(
        f"# Open Summer 2027 internships matching your filters\n\n"
        f"Updated {today} · {len(open_jobs)} roles · {n_dated} with a stated deadline · {n_rolling} rolling\n\n"
        f"**Apply by:** the posting's stated deadline · _rolling_ = reviewed as applications arrive, apply early · "
        f"_—_ = no deadline stated (most big-tech internships), treat as rolling.\n\n"
        f"## ⏰ Deadlines in the next 14 days ({len(closing)})\n\n{closing_md}\n\n"
        f"## ⭐ Top companies ({len(top)})\n\n{rows(top)}\n\n## Everyone else ({len(rest)})\n\n{rows(rest)}\n")


def rows_ordered(js):
    out = ["| Apply by | Company | Role | Location |", "|---|---|---|---|"]
    for v in js:
        loc = ", ".join(l for l in v["locations"] if l)[:60].replace("|", "/")
        out.append(f"| {apply_by(v)} | {v['company']} | [{v['title'].replace('|', '/')}]({v['url']}) | {loc} |")
    return "\n".join(out)


def _days_ago(date_str):
    return (datetime.now(timezone.utc).date() - datetime.strptime(date_str, "%Y-%m-%d").date()).days


if __name__ == "__main__":
    if "--digest" in sys.argv:
        digest()
    else:
        poll(dry_run="--dry-run" in sys.argv)
