# Job Tracker

A private, local job-application tracker that tells you **which kinds of roles you actually succeed in** — and
what to do today.

- **Overview** – today's priorities (follow-ups, likely-ghosted applications, due reminders, upcoming interviews,
  thank-you notes), your active pipeline, upcoming interviews and key insights.
- **Applications** – a drag-and-drop board and a sortable table. Every application has a detail panel with a
  stage timeline (schedule interviews with future dates, edit or remove stages), the job description with skills
  and requirement detection, reminders and editable role dimensions.
- **Analytics** – conversion rates between every pipeline step (application → response → first interview →
  later round → offer), median time to response, response/interview/offer rate by job family or any other
  dimension, a funnel, a flow diagram, the Role Success Scorecard and a two-dimension heatmap.
- **Quick add** – press **N** anywhere, paste a job description, and title, company, seniority, industry, work
  permit, language, work mode and skills are filled in. Uncertain values are highlighted for review.
- **Consistent filters** – job family, industry, seniority, location, channel and date range apply to the board,
  the table, the insights and every chart.

Everything runs on your machine. Your data lives in a local SQLite file that is never committed.

> Coming next: **Discover** (CV-vs-job fit analysis with a local Ollama model, separating essential from preferred
> requirements, and a target CV/cover letter) and **Career development** (interview learning journal,
> personalised practice, story bank, skills report and industry notes).

## Quick start

You only need Python 3.10+. The web interface is pre-built and ships with the package.

```bash
git clone https://github.com/<you>/job-tracker.git
cd job-tracker
python -m venv .venv
source .venv/bin/activate            # Windows Git Bash: source .venv/Scripts/activate
python -m pip install -r requirements.txt
python -m jobtracker
```

Your browser opens at http://localhost:8501. Load the sample data from **Settings → Import & export** to look
around, or import your own spreadsheet there. Add your skills under **Settings → Profile & goals** to get
skills-match scores.

Options: `python -m jobtracker --port 8600 --no-browser`. To keep the database elsewhere, set
`JOBTRACKER_DB=/path/to/tracker.db`.

## How things are worked out

| Dimension | Source |
|---|---|
| Job family (40+) | Keywords in the job title, `config/categories.yaml` |
| Location group | Keywords in the location |
| Seniority | Title keywords (intern, graduate, junior, senior…), then years of experience asked in the description |
| Industry (28) | Company name lists, then description keywords, `config/dimensions.yaml` |
| Company size | Known-company list |
| Work permit, language, work mode | Phrases in the job description (including postings written in German) |
| Skills match | Skills found in the description that are in your profile |

Every inferred value shows as **Auto** and keeps updating if you edit the description or the rules. Pick a value
to set it yourself. Rules can be edited in **Settings → Categorisation rules**, which also lists titles and
companies that don't match any rule yet.

## Metrics

| Metric | Definition |
|---|---|
| Application → response | Any reply, including rejections |
| Application → first interview | Reached Interview or later, even if rejected afterwards |
| First interview → later round | Of applications with an interview, share that reached a final round or offer |
| Interview → offer | Of applications with an interview, share that got an offer |
| Median time to response | Days from applying to the first recorded reply (needs stages recorded with their real date) |
| Adjusted rate (scorecard) | (successes + 10 × your average) ÷ (applications + 10) |
| 95% range | Wilson score interval |

Unanswered applications younger than 21 days are left out of rates, since they haven't had time to get a reply.
Change this in Settings.

## Importing a spreadsheet

The importer finds the header row automatically and recognises common column names: Company, Position/Role,
Date Applied, Date Posted, Application Status, Final Status, Location/Details, Job Description, Source/Channel,
Hiring Manager/Contact, Link, Seniority, Industry, Company Size, Work Mode, CV Version, Fit, Salary, Notes.
Dates can be ISO (2026-03-01) or day-first (01.03.2026). The Excel export can be imported again.

## Development

```
jobtracker/
  api.py            FastAPI app (serves /api and the built interface)
  service.py        cached, enriched view of the data + shared filters
  storage.py        SQLite: applications, stage history, reminders, settings
  analysis.py       enrichment, conversion metrics, scorecard, funnel, flow (pure pandas)
  notifications.py  today's priorities
  dimensions.py     seniority / industry / permit / language / skills inference
  categorise.py     job family / location rules
  importer.py       Excel/CSV import and export
  web/              built interface (generated, committed so users don't need Node)
frontend/           React + TypeScript + Tailwind source
config/             editable rules
tests/              pytest suite
```

Backend tests: `python -m pip install pytest httpx && python -m pytest`

Working on the interface (needs Node 18+):

```bash
python -m jobtracker --no-browser      # API on :8501
cd frontend && npm install && npm run dev   # interface on :5173, proxies /api
npm run build                          # writes the production build to jobtracker/web
```

## License

MIT
