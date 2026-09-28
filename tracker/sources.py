"""One fetcher per job source. Each returns a list of Job objects (unfiltered)."""
import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import config

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) internship-tracker/1.0"


@dataclass
class Job:
    source: str            # e.g. "greenhouse", "simplify"
    company: str
    job_id: str
    title: str
    url: str
    locations: list = field(default_factory=list)
    posted_ts: float | None = None
    text: str = ""         # qualifications/description snippet, when available
    degrees: list = field(default_factory=list)   # Simplify only
    sponsorship: str = ""  # Simplify only
    terms: list = field(default_factory=list)     # Simplify only
    category: str = ""     # Simplify only

    @property
    def uid(self):
        return f"{self.source}:{self.company.lower()}:{self.job_id}"


def http(url, data=None, headers=None, retries=2):
    body = json.dumps(data).encode() if data is not None else None
    hdrs = {"User-Agent": UA, "Accept": "application/json, text/html"}
    if body:
        hdrs["Content-Type"] = "application/json"
    hdrs.update(headers or {})
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=body, headers=hdrs)
            with urllib.request.urlopen(req, timeout=40) as r:
                return r.read().decode("utf-8", "replace")
        except Exception:
            if attempt == retries:
                raise
            time.sleep(2 * (attempt + 1))


def http_json(url, data=None):
    return json.loads(http(url, data))


# --- ATS job boards ---------------------------------------------------------

def greenhouse(token, name):
    d = http_json(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs")
    return [Job("greenhouse", name, str(j["id"]), j["title"], j["absolute_url"],
                [(j.get("location") or {}).get("name", "")],
                _iso(j.get("first_published") or j.get("updated_at")))
            for j in d.get("jobs", [])]


def ashby(token, name):
    d = http_json(f"https://api.ashbyhq.com/posting-api/job-board/{token}")
    out = []
    for j in d.get("jobs", []):
        if j.get("isListed") is False:
            continue
        locs = [j.get("location", "")] + [s.get("location", "") for s in j.get("secondaryLocations", [])]
        out.append(Job("ashby", name, j["id"], j["title"], j["jobUrl"], locs, _iso(j.get("publishedAt"))))
    return out


def lever(token, name):
    d = http_json(f"https://api.lever.co/v0/postings/{token}?mode=json")
    return [Job("lever", name, j["id"], j["text"], j["hostedUrl"],
                j.get("categories", {}).get("allLocations") or [j.get("categories", {}).get("location", "")],
                (j.get("createdAt") or 0) / 1000 or None)
            for j in d]


def workday(key, name, pages=5):
    tenant, shard, site = key
    base = f"https://{tenant}.{shard}.myworkdayjobs.com"
    out = []
    for p in range(pages):
        d = http_json(f"{base}/wday/cxs/{tenant}/{site}/jobs",
                      {"appliedFacets": {}, "limit": 20, "offset": p * 20, "searchText": "intern"})
        posts = d.get("jobPostings", [])
        for j in posts:
            if "externalPath" not in j:
                continue
            # locationsText is often just "2 Locations"; the path carries the primary one.
            parts = j["externalPath"].split("/")
            primary = parts[2].replace("-", " ") if len(parts) > 3 else ""
            text = j.get("locationsText", "")
            out.append(Job("workday", name, j["externalPath"].rsplit("_", 1)[-1], j["title"],
                           f"{base}/{site}{j['externalPath']}", [primary] if "Locations" in text else [text]))
        if len(posts) < 20:
            break
    return out


# --- Big tech custom career sites -------------------------------------------

def amazon():
    out, offset = [], 0
    while True:
        q = urllib.parse.urlencode({"base_query": "intern", "country": "USA", "result_limit": 100,
                                    "offset": offset, "sort": "recent"})
        d = http_json(f"https://www.amazon.jobs/en/search.json?{q}")
        for j in d.get("jobs", []):
            out.append(Job("amazon", "Amazon", str(j["id_icims"]), j["title"],
                           "https://www.amazon.jobs" + j["job_path"],
                           [j.get("normalized_location") or j.get("location", "")],
                           _parse_date(j.get("posted_date")),
                           _strip_html(j.get("basic_qualifications", ""))))
        offset += 100
        if offset >= min(d.get("hits", 0), 500):
            return out


def microsoft():
    out, start = [], 0
    while True:
        q = urllib.parse.urlencode({"domain": "microsoft.com", "query": "intern", "location": "United States",
                                    "start": start, "sort_by": "timestamp"})
        d = http_json(f"https://apply.careers.microsoft.com/api/pcsx/search?{q}")["data"]
        pos = d.get("positions", [])
        for j in pos:
            out.append(Job("microsoft", "Microsoft", str(j["id"]), j["name"],
                           "https://apply.careers.microsoft.com" + j["positionUrl"],
                           j.get("standardizedLocations") or j.get("locations", []), j.get("postedTs")))
        start += len(pos)
        if not pos or start >= min(d.get("count", 0), 300):
            return out


def google(max_pages=10):
    out = []
    for page in range(1, max_pages + 1):
        q = urllib.parse.urlencode({"location": "United States", "target_level": "INTERN_AND_APPRENTICE",
                                    "sort_by": "date", "page": page})
        html = http(f"https://www.google.com/about/careers/applications/jobs/results/?{q}")
        m = re.search(r"AF_initDataCallback\(\{key: 'ds:1', hash: '\d+', data:(.*?), sideChannel: \{\}\}\);", html, re.S)
        if not m:
            raise RuntimeError("Google page layout changed (ds:1 block not found)")
        data = json.loads(m.group(1))
        jobs = data[0] or []
        for j in jobs:
            slug = re.sub(r"[^a-z0-9]+", "-", j[1].lower()).strip("-")
            locs = [loc[0] for loc in (j[9] or [])]
            text = " ".join(_strip_html((x or [None, ""])[1] or "") for x in (j[4], j[15]))
            out.append(Job("google", "Google", j[0], j[1],
                           f"https://www.google.com/about/careers/applications/jobs/results/{j[0]}-{slug}",
                           locs, (j[12] or [None])[0], text))
        if len(jobs) < 20:
            return out
    return out


# --- Aggregator backstop ----------------------------------------------------

SIMPLIFY_URL = "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/dev/.github/scripts/listings.json"


def simplify():
    out = []
    for j in http_json(SIMPLIFY_URL):
        if not j.get("active") or not j.get("is_visible", True):
            continue
        out.append(Job("simplify", j["company_name"], j["id"], j["title"], j["url"],
                       j.get("locations", []), j.get("date_posted"), degrees=j.get("degrees") or [],
                       sponsorship=j.get("sponsorship", ""), terms=j.get("terms") or [], category=j.get("category", "")))
    return out


def all_fetchers():
    """(name, zero-arg callable) for every source."""
    f = [(f"greenhouse:{t}", lambda t=t, n=n: greenhouse(t, n)) for t, n in config.GREENHOUSE.items()]
    f += [(f"ashby:{t}", lambda t=t, n=n: ashby(t, n)) for t, n in config.ASHBY.items()]
    f += [(f"lever:{t}", lambda t=t, n=n: lever(t, n)) for t, n in config.LEVER.items()]
    f += [(f"workday:{k[0]}", lambda k=k, n=n: workday(k, n)) for k, n in config.WORKDAY.items()]
    f += [("amazon", amazon), ("microsoft", microsoft), ("google", google), ("simplify", simplify)]
    return f


# --- helpers ----------------------------------------------------------------

def _iso(s):
    if not s:
        return None
    from datetime import datetime
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _parse_date(s):
    from datetime import datetime
    try:
        return datetime.strptime(s, "%B %d, %Y").timestamp()
    except (TypeError, ValueError):
        return None


def _strip_html(s):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s or "")).strip()
