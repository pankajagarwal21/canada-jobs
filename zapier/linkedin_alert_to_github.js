// Zapier "Code by Zapier" (JavaScript) step.
// Input data (map these in the Zap):
//   body   = Gmail "Body Plain"
//   date   = Gmail "Date"
//   token  = a GitHub fine-grained token (only this repo, "Contents: read and write")
// Adds the Canadian jobs in one LinkedIn job-alert email to jobs.json in the repo.

const REPO = "pankajagarwal21/canada-jobs";
const FILE = "jobs.json";
const REL = /project|program|delivery|scrum|agile|product(?!ion)|business (systems? )?analyst|\bqa\b|quality assurance|test|portfolio manag|chef(fe)? de projet|gestionnaire de projet|analyste de projet|\bsdet\b/i;
const PROV = new Set(["AB","BC","MB","NB","NL","NS","NT","NU","ON","PE","QC","SK","YT"]);
const JUNK = /^(-{3,}|https?:\/\/.*|see all jobs.*|view jobs.*|manage alerts.*|your job alert.*|\d+\+? new jobs.*|jobs? you may be interested in.*)$/i;
const BADGE = /^(top applicant|actively (recruiting|hiring)|easy apply|promoted|new|.*(connection|alumni).*|be an early applicant|apply with .*|\$?CA\$.*)$/i;
const clean = s => s.replace(/[͏​‌‍ ⠀]+/g, " ").replace(/\s+/g, " ").trim();

function parse(body, dateStr) {
  const d = new Date(dateStr);
  const posted = isNaN(d) ? "" : d.toISOString().slice(0, 10);
  const re = /View job:\s*https:\/\/www\.linkedin\.com\/comm\/jobs\/view\/(\d+)/gi;
  const out = [];
  let last = 0, m;
  while ((m = re.exec(body))) {
    const lines = body.slice(last, m.index).split(/\r?\n/).map(clean)
      .filter(l => l && !JUNK.test(l)).filter(l => !BADGE.test(l));
    last = re.lastIndex;
    if (lines.length < 3) continue;
    const [title, company, location] = lines.slice(-3);
    const prov = (location.match(/,\s*([A-Z]{2})\b/) || [])[1];
    const canada = /canada/i.test(location) || (prov && PROV.has(prov));
    if (!canada || !REL.test(title)) continue;
    out.push({
      title, company, location,
      province: prov && PROV.has(prov) ? prov : "",
      arrangement: /remote/i.test(location) ? "Remote" : /hybrid/i.test(location) ? "Hybrid" : "",
      job_type: "", posted,
      url: `https://www.linkedin.com/jobs/view/${m[1]}/`,
      source: "LinkedIn",
    });
  }
  return out;
}

async function run(inputData, fetchFn) {
  const found = parse(inputData.body || "", inputData.date);
  if (!found.length) return { added: 0 };
  const api = `https://api.github.com/repos/${REPO}/contents/${FILE}`;
  const headers = {
    Authorization: `Bearer ${inputData.token}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "canada-jobs-zap",
  };
  for (let attempt = 0; attempt < 3; attempt++) {
    const r = await fetchFn(api, { headers });
    if (!r.ok) throw new Error(`GitHub read failed: ${r.status}`);
    const f = await r.json();
    const jobs = JSON.parse(Buffer.from(f.content, "base64").toString("utf8"));
    const have = new Set(jobs.map(j => j.url));
    const seen = new Set();
    const fresh = found.filter(j => !have.has(j.url) && !seen.has(j.url) && seen.add(j.url));
    if (!fresh.length) return { added: 0 };
    const merged = fresh.concat(jobs).sort((a, b) => (b.posted || "").localeCompare(a.posted || ""));
    const put = await fetchFn(api, {
      method: "PUT", headers,
      body: JSON.stringify({
        message: `Add ${fresh.length} LinkedIn job(s) from alert email`,
        content: Buffer.from(JSON.stringify(merged, null, 1) + "\n").toString("base64"),
        sha: f.sha,
      }),
    });
    if (put.ok) return { added: fresh.length };
    if (put.status !== 409 && put.status !== 422) throw new Error(`GitHub write failed: ${put.status}`);
    // file changed under us: re-read and try again
  }
  throw new Error("Could not update jobs.json after 3 tries");
}

module.exports = { parse, run };
// In Zapier, replace the line above with:  return await run(inputData, fetch);
