"""Decide whether a job is relevant, and attach warning flags."""
import re

from . import config

_any = lambda pats, s: any(re.search(p, s) for p in pats)

US_STATES = set("""AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH
NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC""".split())
US_HINTS = [r"united states", r"\busa?\b", r"\bu\.s\.", r"\bamer", r"\bnyc\b", r"\bsf\b", r"new york",
            r"san francisco", r"seattle", r"bellevue", r"redmond", r"mountain view", r"sunnyvale",
            r"palo alto", r"menlo park", r"san jose", r"santa clara", r"los angeles", r"austin",
            r"boston", r"cambridge, ma", r"chicago", r"atlanta", r"denver", r"pittsburgh",
            r"washington", r"san diego", r"remote$", r"^remote\b(?!.*(canada|uk|europe|india|emea))"]
NON_US = [r"canada", r"toronto", r"vancouver", r"montreal", r"ontario", r"london", r"united kingdom",
          r"\buk\b", r"ireland", r"dublin", r"\bindia\b", r"bangalore", r"bengaluru", r"hyderabad", r"pune",
          r"germany", r"berlin", r"munich", r"france", r"paris", r"zurich", r"switzerland", r"singapore",
          r"japan", r"tokyo", r"australia", r"sydney", r"china", r"shanghai", r"beijing", r"israel",
          r"tel aviv", r"netherlands", r"amsterdam", r"poland", r"warsaw", r"spain", r"madrid",
          r"brazil", r"mexico", r"korea", r"seoul", r"taiwan", r"hong kong", r"romania", r"czech",
          r"prague", r"sweden", r"stockholm", r"denmark", r"copenhagen", r"emea", r"apac", r"italy",
          r"belgium", r"austria", r"vietnam", r"philippines", r"egypt", r"turkey", r"serbia", r"europe"]


SIMPLIFY_CATEGORIES = {"AI/ML/Data", "Software", "Software Engineering",
                       "Data Science, AI & Machine Learning"}


def is_us(locations):
    locs = [l.strip() for l in locations if l and l.strip()]
    if not locs:
        return True
    for l in locs:
        low = l.lower()
        if _any(US_HINTS, low) or any(t in US_STATES for t in re.findall(r"\b([A-Z]{2})\b", l)):
            return True
    return not any(_any(NON_US, l.lower()) for l in locs)


def term_ok(job):
    t = job.title.lower()
    if job.terms and "N/A" not in job.terms:
        return config.TARGET_TERM in job.terms
    if "2027" not in t and re.search(r"20(2[4-6])", t):
        return False              # Fall 2026 / Summer 2026 leftovers
    if re.search(r"\b(fall|spring|autumn)\b", t) and "summer" not in t:
        return False
    if re.search(r"\bwinter\b", t) and "summer" not in t:
        return False
    return True


def degree_flags(job):
    """Returns (drop, flags)."""
    t, flags = job.title.lower(), []
    ms = bool(re.search(r"\b(ms|m\.s\.|master'?s?|graduate|grad)\b", t))
    phd_only = (bool(re.search(r"\bph\.?d\b", t)) and not ms) or (job.degrees == ["PhD"])
    undergrad_only = bool(re.search(r"\bundergrad|\bbs,|\bb\.s\.,|\bbachelor'?s? only", t)) and not ms
    if phd_only:
        flags.append("PhD-only")
    if undergrad_only:
        flags.append("undergrad-only")
    drop = (phd_only and config.DROP_PHD_ONLY) or (undergrad_only and config.DROP_UNDERGRAD_ONLY)
    return drop, flags


MONTHS = {m: i + 1 for i, m in enumerate(
    "jan feb mar apr may jun jul aug sep oct nov dec".split())}


def grad_window_flag(text):
    """Flag when the posting states a graduation window that excludes Dec 2027."""
    for sent in re.split(r"(?<=[.;])\s+|\n", text or ""):
        if "graduat" not in sent.lower():
            continue
        dates = [(int(y), MONTHS.get((m or "")[:3].lower(), 6))
                 for m, y in re.findall(r"(?:(\b[A-Za-z]{3,9})\.?\s+)?(20[2-3]\d)\b", sent)]
        if len(dates) >= 2:
            lo, hi = min(dates), max(dates)
            if not lo <= (config.GRAD_YEAR, config.GRAD_MONTH) <= hi:
                return f"grad window {lo[1]}/{lo[0]}–{hi[1]}/{hi[0]}"
    return None


def evaluate(job):
    """Returns (keep, flags)."""
    t = job.title.lower()
    if not _any(config.INTERN_PATTERNS, t):
        return False, []
    if _any(config.EXCLUDE_PATTERNS, t):
        return False, []
    if not (_any(config.ROLE_PATTERNS, t) or job.category in SIMPLIFY_CATEGORIES):
        return False, []
    if _any(NON_US, t) and not _any(US_HINTS, t):
        return False, []          # location named in the title, e.g. "Intern - Berlin"
    if not term_ok(job) or not is_us(job.locations):
        return False, []
    if job.sponsorship == "U.S. Citizenship is Required":
        return False, []
    drop, flags = degree_flags(job)
    if drop:
        return False, flags
    if job.sponsorship == "Does Not Offer Sponsorship":
        flags.append("no sponsorship (CPT usually OK — verify)")
    if re.search(r"u\.?s\.? citizen|security clearance", (job.text or "").lower()):
        flags.append("mentions citizenship/clearance")
    g = grad_window_flag(job.text)
    if g:
        flags.append(g)
    return True, flags
