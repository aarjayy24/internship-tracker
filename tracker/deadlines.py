"""Find an application deadline in a job posting: an explicit date, or "rolling"."""
import html
import re
from datetime import date, datetime, timedelta

MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}
MON = r"(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"

TRIGGER = re.compile(
    r"deadline|apply by|closing date|closes on|no later than|expir"
    r"|complete your application (?:before|by)"
    r"|applications? (?:\w+ ){0,4}(?:until|through|by|before)"
    r"|(?:posting|position|role|job|requisition) (?:\w+ ){0,4}(?:close|closes|closing|open until|open through)"
    r"|submit (?:\w+ ){0,4}(?:by|before)", re.I)
ROLLING = re.compile(
    r"rolling basis|ongoing basis|until (?:the )?(?:position|role|job|req\w*) (?:is|has been) filled"
    r"|until filled|rolling admission", re.I)
IGNORE = re.compile(r"graduat|start date|internship (?:dates|runs|begins)|program dates", re.I)

DATE_PATTERNS = [
    (re.compile(MON + r"\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?", re.I), "mdy"),
    (re.compile(r"(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?" + MON + r",?\s*(\d{4})?", re.I), "dmy"),
    (re.compile(r"\b(20\d\d)-(\d{2})-(\d{2})\b"), "iso"),
    (re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{2,4})\b"), "us"),
]


def _mk(y, m, d, today):
    try:
        if y is None:   # no year given: pick the next plausible occurrence
            dt = date(today.year, m, d)
            if dt < today - timedelta(days=60):
                dt = date(today.year + 1, m, d)
            return dt
        y = int(y)
        return date(y + 2000 if y < 100 else y, m, d)
    except ValueError:
        return None


def _dates_in(sentence, today):
    found = []
    for rx, kind in DATE_PATTERNS:
        for m in rx.finditer(sentence):
            g = m.groups()
            if kind == "mdy":
                dt = _mk(g[2], MONTHS[g[0][:3].lower()], int(g[1]), today)
            elif kind == "dmy":
                dt = _mk(g[2], MONTHS[g[1][:3].lower()], int(g[0]), today)
            elif kind == "iso":
                dt = _mk(g[0], int(g[1]), int(g[2]), today)
            else:
                dt = _mk(g[2], int(g[0]), int(g[1]), today)
            if dt and today - timedelta(days=30) <= dt <= today + timedelta(days=400):
                found.append((m.start(), dt))
    return [d for _, d in sorted(found)]


def to_text(s):
    s = html.unescape(s or "")
    s = re.sub(r"<\s*(br|/p|/li|/h\d|/div)[^>]*>", ". ", s, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip()


def find(text, explicit=None, today=None):
    """Returns (deadline 'YYYY-MM-DD' | None, rolling: bool)."""
    today = today or date.today()
    if explicit:
        try:
            return datetime.fromisoformat(str(explicit).replace("Z", "+00:00")).date().isoformat(), False
        except ValueError:
            pass
    text = to_text(text)
    for sent in re.split(r"(?<=[.!?;])\s+", text):
        if IGNORE.search(sent) or not TRIGGER.search(sent):
            continue
        ds = _dates_in(sent[TRIGGER.search(sent).start():], today)
        if ds:
            return ds[0].isoformat(), False
    return None, bool(ROLLING.search(text))
