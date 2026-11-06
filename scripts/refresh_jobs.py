#!/usr/bin/env python3
"""Refresh jobs.json with Canada-eligible remote listings from Jobicy.

- Listings from other sources already in jobs.json (Indeed, ZipRecruiter, ...) are kept.
- Previous Jobicy listings are replaced by the fresh fetch, so closed ones drop off.
- Any listing posted more than MAX_AGE_DAYS (21) days ago is removed.
- If the API cannot be reached, the file is left untouched and the script exits with an error.

Jobicy asks integrators to poll at most hourly and to keep the original Jobicy URL
and source attribution, which this script does (one run per day).
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

API = "https://jobicy.com/api/v2/remote-jobs"
SOURCE = "Jobicy"
KEYWORDS = ["project manager", "scrum master", "delivery manager",
            "program manager", "product manager", "product owner", "agile",
            "business analyst", "quality assurance", "qa engineer",
            "test automation", "software tester"]
TITLE_RE = re.compile(
    r"project (manager|lead|coordinator)|program manager|delivery (manager|lead)|"
    r"scrum|agile|product (manager|owner)|technical program|release manager|"
    r"business (systems? )?analyst|\bqa\b|quality assurance|\btester\b|\bsdet\b|"
    r"test(ing)? (engineer|analyst|automation|lead)|automation test|test automation",
    re.I,
)
GEO_OK_RE = re.compile(r"canada|anywhere|north america|americas", re.I)
MAX_AGE_DAYS = 21
UA = "canada-jobs-board/1.0 (+https://pankajagarwal21.github.io/canada-jobs/)"
JOBS_FILE = Path(__file__).resolve().parent.parent / "jobs.json"


def http_get_json(params, retries=3):
    url = API + "?" + urllib.parse.urlencode(params)
    last = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # network, HTTP or JSON error
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Request failed for {url}: {last}")


def find_canada_slug(locations_payload):
    """Look for a geo slug whose name mentions Canada in the ?get=locations response."""
    def walk(x):
        if isinstance(x, dict):
            slug = x.get("geoSlug") or x.get("slug")
            name = x.get("geoName") or x.get("name") or ""
            if slug and "canada" in (str(name) + " " + str(slug)).lower():
                yield str(slug)
            for v in x.values():
                yield from walk(v)
        elif isinstance(x, list):
            for v in x:
                yield from walk(v)
    return next(walk(locations_payload), None)


def to_record(j, trusted_geo):
    title = str(j.get("jobTitle") or "").strip()
    url = str(j.get("url") or "").strip()
    if not title or not url.startswith("http") or not TITLE_RE.search(title):
        return None
    geo = j.get("jobGeo") or ""
    if isinstance(geo, list):
        geo = ", ".join(str(g) for g in geo)
    geo = str(geo).strip()
    if not trusted_geo and not GEO_OK_RE.search(geo):
        return None
    jtype = j.get("jobType") or ""
    if isinstance(jtype, list):
        jtype = ", ".join(str(t).replace("-", " ").title() for t in jtype)
    posted = str(j.get("pubDate") or "")[:10]
    rec = {
        "title": title,
        "company": str(j.get("companyName") or "").strip(),
        "location": "Remote (" + (geo or "Canada") + ")",
        "province": "",
        "arrangement": "Remote",
        "job_type": str(jtype),
        "posted": posted,
        "url": url,
        "source": SOURCE,
    }
    # Only keep salary when it is stated in CAD per year, which is what the board filters on.
    if str(j.get("salaryCurrency") or "").upper() == "CAD" and str(j.get("salaryPeriod") or "").lower() in ("yearly", "year", "annual"):
        for src, dst in (("salaryMin", "salary_min"), ("salaryMax", "salary_max")):
            v = j.get(src)
            if isinstance(v, (int, float)) and v > 0:
                rec[dst] = int(v)
    return rec


def fetch_fresh(get=http_get_json):
    slug = None
    try:
        slug = find_canada_slug(get({"get": "locations"}))
    except Exception as e:
        print(f"Could not read location list ({e}); filtering by job text instead.", file=sys.stderr)
    seen, out = set(), []
    for kw in KEYWORDS:
        params = {"count": 100, "tag": kw}
        if slug:
            params["geo"] = slug
        payload = get(params)  # raises if it cannot be fetched, which aborts the run
        for j in payload.get("jobs", []) or []:
            rec = to_record(j, trusted_geo=bool(slug))
            if rec and rec["url"] not in seen:
                seen.add(rec["url"])
                out.append(rec)
        time.sleep(1)
    return out, slug


def merge(existing, fresh, today):
    cutoff = today - timedelta(days=MAX_AGE_DAYS)
    keep = []
    for j in existing:
        if j.get("source") == SOURCE:
            continue  # replaced by the fresh fetch
        p = j.get("posted") or ""
        try:
            if p and datetime.strptime(p, "%Y-%m-%d").date() < cutoff:
                continue
        except ValueError:
            pass
        keep.append(j)
    fresh = [j for j in fresh if not _too_old(j, cutoff)]
    merged = keep + fresh
    merged.sort(key=lambda j: j.get("posted") or "", reverse=True)
    return merged


def _too_old(j, cutoff):
    try:
        return bool(j.get("posted")) and datetime.strptime(j["posted"], "%Y-%m-%d").date() < cutoff
    except ValueError:
        return False


def main():
    existing = json.loads(JOBS_FILE.read_text(encoding="utf-8")) if JOBS_FILE.exists() else []
    fresh, slug = fetch_fresh()
    merged = merge(existing, fresh, datetime.now(timezone.utc).date())
    new_text = json.dumps(merged, ensure_ascii=False, indent=1) + "\n"
    old_text = JOBS_FILE.read_text(encoding="utf-8") if JOBS_FILE.exists() else ""
    print(f"geo slug: {slug or 'none (text filter)'}; fresh {SOURCE}: {len(fresh)}; total: {len(merged)}")
    if new_text != old_text:
        JOBS_FILE.write_text(new_text, encoding="utf-8")
        print("jobs.json updated")
    else:
        print("no changes")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
