# Job Tracker

Track your job applications and find out **which kinds of roles you actually succeed in**.

Most trackers count how many applications you've sent. This one works out your personal success
rate across every dimension of a role: job family, seniority, industry, location, company size,
work permit and language requirements, application channel, how soon after posting you applied,
and how well your skills match the job description. Then it tells you where to spend your next
applications.

It's a [Streamlit](https://streamlit.io) app backed by a local SQLite file. Your data never leaves
your machine.

## Features

### Role Success Scorecard
- Success rate for every value of 14 dimensions: job family, seniority, industry, location, company size,
  work permit requirement, language requirement, work mode, application channel, days between posting
  and applying, skills match with the job description, CV version, your own fit rating, and weekday.
- Choose what counts as success: positive response (screening or further), interview, or any reply.
- **Adjusted rates** pull small groups towards your average so 1 out of 2 doesn't outrank 5 out of 30, and
  95% intervals show how sure each number is. Every group gets a verdict: *Strength*, *Promising*,
  *About average*, *Below average*, *Weak spot* or *Too few to tell*.
- "Where you do best / where you struggle" across all dimensions at once, and a heatmap to combine any two
  (for example job family × seniority).
- Recent applications that haven't had time to get a reply are left out, so they don't drag rates down.

### Job description analysis
- Paste the posting and the app detects **skills**, **years of experience**, **language requirements**
  (including postings written in German), **work permit / sponsorship** wording, **work mode** and seniority.
- Add your skills once in Settings to get a **match score** for every posting, a list of the skills you're
  missing most often, and success rates for postings that mention each skill.

### Spreadsheet-style editing
- Edit applications directly in a grid like Excel: change a status, fix a date, retag a job family,
  add rows at the bottom, delete rows. Changes are saved in one go, and status changes are logged with the date.
- A details panel per application for the job description, notes, stage history and analysis.
- Inferred values (seniority, industry, ...) show as *Auto*; pick a value to override it for that application.

### Pipeline and follow-ups
- Dashboard with takeaways, a stage **funnel** with conversion and drop-off per step, a **flow (Sankey) diagram**
  of where applications end up, applications per month, and weekly pace against your goal.
- Stage tracking: Applied → Screening → Interview → Final interview → Offer, plus Rejected, Ghosted, Withdrawn.
- Follow-ups page lists applications that have gone quiet, with one-click *Followed up / Rejected / Ghosted*.
- Duplicate warning when you add a role you've already applied to, and a list of earlier applications to the
  same company.

### Import and export
- Import an existing Excel or CSV tracker; the header row and common column names are detected automatically.
- Export everything to Excel (applications + stage history), which can be imported again. Download a database
  backup.

## Quick start

```bash
git clone https://github.com/<you>/job-tracker.git
cd job-tracker
python -m venv .venv
source .venv/bin/activate          # Windows Git Bash: source .venv/Scripts/activate
pip install -r requirements.txt
python -m streamlit run app.py
```

The app opens at http://localhost:8501. Load the fictional sample data to look around, or go to
**Import & export** and upload your own tracker. Then add your skills under **Settings**.

> On Windows, if `streamlit` isn't found, use `python -m streamlit run app.py`.

## Getting the most out of it

The scorecard gets more useful the more you record per application:

| Record this | To learn |
|---|---|
| Date posted | Whether applying early improves your odds |
| Job description | Skills match, language and permit requirements, seniority |
| Channel (LinkedIn, referral, ...) | Which channels work for you |
| Stages as they happen | Where you drop out, and how long companies take to reply |
| CV version | Which CV gets more replies |
| Fit rating (1–5) | Whether your gut feeling about a role is right |

## Importing your tracker

The importer finds the first row that has a company column and a position/role column, and maps these
columns when it finds them (case-insensitive):

| Field | Recognised column names |
|---|---|
| Company | Company, Employer, Organisation |
| Position | Position, Role, Job title, Title |
| Date applied | Date Applied, Application date, Applied on |
| Date posted | Date Posted, Posting date, Posted on |
| Status | Application Status, Status, Stage |
| Final status | Final Status, Outcome, Result |
| Location | Location, City, Country, Details |
| Job description | Job Description, Description, JD |
| Source | Source, Channel, Found via |
| Contact | Hiring Manager, Contact, Recruiter |
| Link | Applicant Portal, URL, Link |
| Also | Seniority, Industry, Company Size, Work Mode, CV Version, Fit, Salary, Notes |

Statuses such as *Submitted*, *Followed up*, *Interview*, *Rejected*, *Ghosted* and *Offer* are mapped to
stages. Dates can be ISO (2026-03-01) or day-first (01.03.2026).

## Tuning the rules

Everything that's inferred comes from editable YAML rules, which you can also edit in the app
(**Settings**):

- [`config/categories.yaml`](config/categories.yaml): job families (from the title) and location groups.
- [`config/dimensions.yaml`](config/dimensions.yaml): seniority, industry (by company name and description
  keywords), company size, work permit and language phrases, work mode, and the skills list.

Settings shows which titles and companies don't match any rule yet, so you know what to add.

## Your data and git

Your applications, skills and settings live in `data/tracker.db`, which is in `.gitignore`. The repo only
ships fictional sample data. To keep the database elsewhere, set `JOBTRACKER_DB=/path/to/tracker.db`.
Databases from older versions are upgraded automatically.

## How metrics are defined

| Metric | Definition |
|---|---|
| Any reply | Applications with any reply, including rejections ÷ applications |
| Positive response | Reached Screening or later (even if rejected afterwards) ÷ applications |
| Interview rate | Reached Interview or later ÷ applications |
| Adjusted rate | (successes + 10 × your average) ÷ (applications + 10) |
| 95% range | Wilson score interval |
| Days to response | Days from applying to the first logged stage after *Applied* |
| Skills match | Skills found in the job description that are in your profile ÷ skills found |

## Project layout

```
app.py                       entry point and navigation
jobtracker/
  storage.py                 SQLite store, migrations, settings
  categorise.py              job family / location rules
  dimensions.py              seniority, industry, size, permit, language, skills from title/company/JD
  importer.py                Excel/CSV import and Excel export
  analysis.py                enrichment, scorecard, funnel, flow, skills, pace (pure pandas)
  ui/                        one module per page
config/                      editable rules
sample_data/                 fictional data + generator
tests/                       pytest suite
```

## Development

```bash
pip install -r requirements.txt pytest
pytest
```

## License

MIT
