# Canada job board

Same idea as the reference board: load scraped job JSON, filter out noise, tag what's worth applying to. Canada-focused.

## Publish on GitHub Pages
Replace the contents of your `canada-jobs` repo with these files:
- `index.html` (the whole app)
- `jobs.json` (starter listings; the page loads it on first visit)

Then Settings > Pages > Deploy from branch `main` / root.

## Adding more jobs (including LinkedIn)
1. Run your LinkedIn (or Indeed) scraper and save its JSON or CSV.
2. Open the site, drop the file onto the upload box, or paste the JSON.
3. Records are merged and de-duplicated. Field names are mapped automatically:
   title/job_title, company/companyName, location, url/jobUrl/link, posted/postedAt/listedAt.

Anything loaded stays in your browser. To make a batch permanent for everyone, merge it into `jobs.json` and commit.

## Notes
- The LinkedIn buttons open pre-filled Canada searches (past 7 days) on linkedin.com.
- LinkedIn has no public jobs API, and its terms restrict automated scraping, so use a scraper you are comfortable running on your own account.
- Starter listings were pulled from Indeed and ZipRecruiter on 2026-11-01. ZipRecruiter rows link to a matching search page, not the individual posting.
