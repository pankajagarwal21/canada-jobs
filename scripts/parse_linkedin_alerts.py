#!/usr/bin/env python3
"""Turn LinkedIn job-alert emails (Gmail search result JSON) into job records."""
import json, re, sys
from email.utils import parsedate_to_datetime

JOB_RE = re.compile(r"View job:\s*https://www\.linkedin\.com/comm/jobs/view/(\d+)", re.I)
BADGES = re.compile(r"^(top applicant|actively (recruiting|hiring)|easy apply|promoted|new|\d+\s+(school alumni|connections?|company alumni)|.*(connection|alumni).*|be an early applicant|apply with .*|\$?CA\$.*)$", re.I)
JUNK = re.compile(r"^(-{3,}|https?://.*|see all jobs.*|view jobs.*|manage alerts.*|your job alert.*|\d+\+? new jobs.*|jobs? you may be interested in.*)$", re.I)
REL = re.compile(r"project|program|delivery|scrum|agile|product|business (systems? )?analyst|\\bqa\\b|quality assurance|test|portfolio manag|chef(fe)? de projet|gestionnaire de projet|analyste de projet|\\bsdet\\b", re.I)
PROV = {"AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"}

def clean(s):
    s = re.sub(r"[͏​‌‍ ⠀]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()

def parse_email(m):
    body = m.get("body_plain") or ""
    try: when = parsedate_to_datetime(m["date"]).date().isoformat()
    except Exception: when = ""
    out, last = [], 0
    for hit in JOB_RE.finditer(body):
        chunk = body[last:hit.start()]
        last = hit.end()
        lines = [clean(l) for l in chunk.splitlines()]
        lines = [l for l in lines if l and not JUNK.match(l)]
        lines = [l for l in lines if not BADGES.match(l)]
        if len(lines) < 3: continue
        title, company, loc = lines[-3], lines[-2], lines[-1]
        out.append({"id": hit.group(1), "title": title, "company": company,
                    "location": loc, "posted": when})
    return out

def in_canada(loc):
    l = loc.lower()
    if "canada" in l: return True
    m = re.search(r",\s*([A-Z]{2})\b", loc)
    return bool(m and m.group(1) in PROV)

def province(loc):
    m = re.search(r",\s*([A-Z]{2})\b", loc)
    return m.group(1) if m and m.group(1) in PROV else ""

def build(messages):
    seen = {}
    for m in messages:
        if ((m.get("from") or {}).get("email") or "").lower() != "jobalerts-noreply@linkedin.com":
            continue
        for j in parse_email(m):
            if not in_canada(j["location"]) or not REL.search(j["title"]): continue
            old = seen.get(j["id"])
            if old and old["posted"] >= j["posted"]: continue
            seen[j["id"]] = j
    recs = []
    for j in seen.values():
        loc = j["location"]
        arr = "Remote" if re.search(r"remote", loc, re.I) else ("Hybrid" if re.search(r"hybrid", loc, re.I) else "")
        recs.append({"title": j["title"], "company": j["company"], "location": loc,
                     "province": province(loc), "arrangement": arr, "job_type": "",
                     "posted": j["posted"], "url": f"https://www.linkedin.com/jobs/view/{j['id']}/",
                     "source": "LinkedIn"})
    recs.sort(key=lambda r: r["posted"], reverse=True)
    return recs

if __name__ == "__main__":
    data = json.load(open(sys.argv[1], encoding="utf-8"))
    msgs = data["results"] if isinstance(data, dict) else data
    recs = build(msgs)
    json.dump(recs, open(sys.argv[2], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(recs), "jobs")
