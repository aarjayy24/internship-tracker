"""Phone push via ntfy.sh and email via Gmail SMTP. Credentials come from env vars."""
import html
import json
import os
import smtplib
import urllib.request
from email.mime.text import MIMEText

from . import config

MAX_PUSHES_PER_RUN = 8   # beyond this, send one summary push instead


def is_tier1(company):
    return company.lower() in config.TIER1


def push(title, message, click=None, priority=3, tags=None):
    topic = os.environ.get("NTFY_TOPIC")
    if not topic:
        print(f"[push skipped: NTFY_TOPIC unset] {title}")
        return
    body = {"topic": topic, "title": title, "message": message, "priority": priority,
            "tags": tags or []}
    if click:
        body["click"] = click
        body["actions"] = [{"action": "view", "label": "Open posting", "url": click}]
    req = urllib.request.Request("https://ntfy.sh/", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=20).read()


def email_enabled():
    return bool(os.environ.get("GMAIL_ADDRESS") and os.environ.get("GMAIL_APP_PASSWORD"))


def email(subject, html_body):
    user, pw = os.environ.get("GMAIL_ADDRESS"), os.environ.get("GMAIL_APP_PASSWORD")
    to = os.environ.get("EMAIL_TO") or user
    if not (user and pw):
        print(f"[email skipped: Gmail secrets unset] {subject}")
        return
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"], msg["From"], msg["To"] = subject, f"Internship Tracker <{user}>", to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as s:
        s.login(user, pw)
        s.sendmail(user, [a.strip() for a in to.split(",")], msg.as_string())


def jobs_table(rows):
    """rows: list of dicts with company, title, url, locations, flags, repost."""
    tr = []
    for r in rows:
        star = "⭐ " if is_tier1(r["company"]) else ""
        flags = "".join(f'<br><span style="color:#b45309">⚠️ {html.escape(f)}</span>' for f in r["flags"])
        rep = ' <span style="color:#6b7280">(reposted)</span>' if r.get("repost") else ""
        due = (f'<br><b style="color:#b91c1c">⏰ Apply by {html.escape(r["deadline"])}</b>' if r.get("deadline")
               else '<br><span style="color:#6b7280">rolling review</span>' if r.get("rolling") else "")
        loc = html.escape(", ".join(l for l in r["locations"] if l)[:120])
        tr.append(f'<tr><td style="padding:6px;border-bottom:1px solid #eee"><b>{star}{html.escape(r["company"])}</b></td>'
                  f'<td style="padding:6px;border-bottom:1px solid #eee"><a href="{html.escape(r["url"])}">'
                  f'{html.escape(r["title"])}</a>{rep}{due}{flags}</td>'
                  f'<td style="padding:6px;border-bottom:1px solid #eee;color:#555">{loc}</td></tr>')
    return ('<table style="border-collapse:collapse;font-family:sans-serif;font-size:14px">'
            '<tr><th align="left">Company</th><th align="left">Role</th><th align="left">Location</th></tr>'
            + "".join(tr) + "</table>")


def announce_new(rows, roles_link):
    """Alert on newly found jobs: one push each (or a summary), plus one email."""
    rows = sorted(rows, key=lambda r: (not is_tier1(r["company"]), r["company"].lower()))
    if len(rows) <= MAX_PUSHES_PER_RUN:
        for r in rows:
            flags = ("\n⚠️ " + "; ".join(r["flags"])) if r["flags"] else ""
            due = (f"\n⏰ Apply by {r['deadline']}" if r.get("deadline")
                   else "\nRolling review: apply early" if r.get("rolling") else "")
            push(f"{'⭐ ' if is_tier1(r['company']) else ''}{r['company']}: new internship",
                 f"{r['title']}\n{', '.join(r['locations'])[:100]}{due}{flags}", click=r["url"],
                 priority=5 if is_tier1(r["company"]) else 4, tags=["briefcase"])
    else:
        top = [r for r in rows if is_tier1(r["company"])]
        head = ", ".join(sorted({r["company"] for r in top})) or ", ".join(sorted({r["company"] for r in rows})[:6])
        push(f"{len(rows)} new internships", f"Including: {head}. " + ("Check your email." if email_enabled() else "Tap to see the list."),
             click=roles_link, priority=5 if top else 4, tags=["briefcase"])
    email(f"🎯 {len(rows)} new internship{'s' if len(rows) != 1 else ''}"
          f"{' — ⭐ ' + ', '.join(sorted({r['company'] for r in rows if is_tier1(r['company'])})) if any(is_tier1(r['company']) for r in rows) else ''}",
          f"<p>New matching postings (apply early — most are reviewed on a rolling basis):</p>"
          f"{jobs_table(rows)}<p><a href=\"{roles_link}\">All open matching roles</a></p>")
