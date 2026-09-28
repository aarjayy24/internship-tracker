"""What to watch and who you are. Edit this file to tune the tracker."""

# --- Your profile -----------------------------------------------------------
GRAD_YEAR, GRAD_MONTH = 2027, 12        # expected graduation: Dec 2027
TARGET_TERM = "Summer 2027"
DROP_PHD_ONLY = True                     # skip roles that explicitly require a PhD
DROP_UNDERGRAD_ONLY = True               # skip roles explicitly for BS/undergrads only

# --- Companies polled directly (fastest alerts) -----------------------------
# token -> display name. Tokens were verified against the live boards.
GREENHOUSE = {
    "anthropic": "Anthropic", "databricks": "Databricks", "stripe": "Stripe",
    "airbnb": "Airbnb", "scaleai": "Scale AI", "figma": "Figma",
    "robinhood": "Robinhood", "pinterest": "Pinterest", "lyft": "Lyft",
    "discord": "Discord", "reddit": "Reddit", "coinbase": "Coinbase",
    "instacart": "Instacart", "dropbox": "Dropbox", "twitch": "Twitch",
    "roblox": "Roblox", "cloudflare": "Cloudflare", "asana": "Asana",
    "datadog": "Datadog", "nuro": "Nuro", "waymo": "Waymo", "xai": "xAI",
    "gleanwork": "Glean", "janestreet": "Jane Street", "imc": "IMC",
    "sofi": "SoFi", "affirm": "Affirm", "brex": "Brex", "samsara": "Samsara",
}
ASHBY = {
    "openai": "OpenAI", "perplexity": "Perplexity", "notion": "Notion",
    "ramp": "Ramp", "cohere": "Cohere", "replit": "Replit", "harvey": "Harvey",
    "elevenlabs": "ElevenLabs", "linear": "Linear", "supabase": "Supabase",
    "modal": "Modal", "snowflake": "Snowflake", "character": "Character.AI",
    "langchain": "LangChain", "cursor": "Cursor", "sierra": "Sierra",
    "decagon": "Decagon",
}
LEVER = {"palantir": "Palantir", "spotify": "Spotify", "zoox": "Zoox"}
# (tenant, workday host shard, site) -> display name
WORKDAY = {
    ("nvidia", "wd5", "NVIDIAExternalCareerSite"): "NVIDIA",
    ("salesforce", "wd12", "External_Career_Site"): "Salesforce",
    ("adobe", "wd5", "external_experienced"): "Adobe",
    ("intel", "wd1", "External"): "Intel",
    ("capitalone", "wd12", "Capital_One"): "Capital One",
}
# Amazon, Google and Microsoft have custom adapters; everyone else (Meta, Apple,
# thousands more) comes from the SimplifyJobs Summer 2027 list.

# Companies whose alerts get high-priority pushes.
TIER1 = {
    "google", "meta", "amazon", "microsoft", "apple", "nvidia", "openai",
    "anthropic", "google deepmind", "deepmind", "xai", "databricks", "netflix",
    "tesla", "stripe", "snowflake", "salesforce", "adobe", "uber", "airbnb",
    "linkedin", "jane street", "two sigma", "citadel", "scale ai", "perplexity",
}

# --- Role filters (matched against the job title, case-insensitive) ---------
INTERN_PATTERNS = [r"\bintern(ship)?s?\b", r"\bco-?op\b", r"\bstudent researcher\b"]

ROLE_PATTERNS = [
    r"data scien", r"machine learning", r"\bml\b", r"\bai\b", r"\bgenai\b",
    r"artificial intelligence", r"deep learning", r"\bllm", r"\bnlp\b",
    r"computer vision", r"applied scien", r"research (engineer|scientist)",
    r"student researcher", r"software", r"\bsde\b", r"\bswe\b", r"developer",
    r"data engineer", r"analytics", r"data analyst", r"quantitative research",
    r"quant research", r"backend", r"back-end", r"full.?stack", r"platform engineer",
    r"infrastructure engineer", r"software engineering intern", r"security engineer",
]
# Titles containing these are never relevant, even if a role pattern matches.
EXCLUDE_PATTERNS = [
    r"hardware", r"silicon", r"\bsoc\b", r"asic", r"\bfpga\b", r"mechanical",
    r"electrical", r"manufacturing", r"supply chain", r"\bux\b", r"user experience",
    r"product design", r"marketing", r"\bsales\b", r"finance", r"accounting",
    r"legal", r"recruit", r"\bhr\b", r"people ops", r"facilities", r"industrial",
    r"security clearance", r"\bts/sci\b", r"clearance required", r"business undergraduate",
    r"\bstep\b", r"explore program", r"high school", r"new grad", r"\bsenior\b",
    r"\bstaff\b", r"\bprincipal\b", r"\bmanager\b", r"verification", r"physical design",
    r"\btiming\b", r"data center", r"\bts\b", r"\bctj\b", r"\bcustomer\b", r"\bbusiness\b",
    r"operations", r"automation engineer", r"\bcircuit", r"\brf\b", r"analog", r"validation",
]
