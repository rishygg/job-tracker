# Job Tracker

Track your job applications and find out **which kinds of roles you're actually getting traction in**.

Most application trackers are spreadsheets that tell you how many applications you've sent. This one
also answers the questions that matter when a search drags on:

- Which role areas get me replies, and which ones get me interviews?
- Where am I being ghosted, and where do I hear back?
- Does it matter whether I apply through a portal, a recruiter or a referral?
- Which applications should I chase today, and which can I write off?

It's a small [Streamlit](https://streamlit.io) app backed by a local SQLite file. Your data never
leaves your machine.

## Features

- **Dashboard**: response rate, interviews, a stage funnel, applications per month by outcome, and
  plain-language takeaways.
- **Traction breakdown** by role area, location, source or company: response rate, interview rate
  (with a 95% interval, so 1 interview out of 4 isn't mistaken for a trend), and ghost rate.
- **Stage tracking**: Applied → Screening → Interview → Final interview → Offer, plus Rejected,
  Ghosted and Withdrawn. Every change is logged with a date, so the tracker can measure how long
  replies take, and an application that reached interview still counts as one after a rejection.
- **Follow-ups**: lists active applications that have gone quiet, and suggests marking very old ones
  as ghosted (both thresholds are adjustable).
- **Automatic categorising**: job titles and locations are grouped by editable keyword rules in
  [`config/categories.yaml`](config/categories.yaml). The Categories page previews what each rule change
  would do and lists titles that don't match any rule yet. You can override any single application.
- **Import** an existing Excel or CSV tracker. The header row is found automatically (title rows
  and summary tables above it are skipped), and common column names are recognised.

## Quick start

```bash
git clone https://github.com/<you>/job-tracker.git
cd job-tracker
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

The app opens at http://localhost:8501. On first run you can load fictional sample data to look around,
or go to **Import** and upload your own tracker.

## Importing your tracker

The importer looks for a row containing a company column and a position/role column, and maps these
columns when it finds them (case-insensitive):

| Field | Recognised column names |
|---|---|
| Company | Company, Employer, Organisation |
| Position | Position, Role, Job title, Title |
| Date applied | Date Applied, Application date, Applied on |
| Status | Application Status, Status, Stage |
| Final status | Final Status, Outcome, Result |
| Location | Location, City, Country, Details |
| Contact | Hiring Manager, Contact, Recruiter |
| Link | Applicant Portal, URL, Link |
| Source | Source, Channel, Found via |
| Notes | Notes, Comments |

Statuses such as *Submitted*, *Followed up*, *Interview*, *Rejected*, *Ghosted* and *Offer* are mapped
to stages. When a row has both a status and a final status (for example *Interview* then *Rejected*),
both are kept in the history.

Imported rows have no reply dates, so they're left out of the "how long replies take" numbers. Stage
changes you record in the app from then on include dates.

## Your data and git

Your applications live in `data/tracker.db`, which is in `.gitignore`, so it never gets committed. The
repo only ships fictional sample data (`sample_data/`). To keep the database somewhere else, set
`JOBTRACKER_DB=/path/to/tracker.db`.

If you deploy to Streamlit Community Cloud, keep the app private: anyone with the link would see your
data, and the cloud filesystem is reset on redeploys. Export a backup (copy `tracker.db`) first.

## How metrics are defined

| Metric | Definition |
|---|---|
| Response rate | Applications with any reply (including rejections) ÷ applications |
| Interview rate | Applications that reached Interview or later ÷ applications |
| Ghost rate | Ghosted ÷ applications that are no longer active |
| 95% range | Wilson score interval for the interview rate |
| Days to response | Days from applying to the first logged stage after *Applied* |

## Project layout

```
app.py                     Streamlit UI
jobtracker/
  storage.py               SQLite store: applications + stage history
  categorise.py            keyword-rule categoriser
  importer.py              Excel/CSV import with header and column detection
  analysis.py              metrics, breakdowns, funnel, follow-ups, insights (pure pandas)
config/categories.yaml     editable categorisation rules
sample_data/               fictional data + the script that generates it
tests/                     pytest suite
```

## Development

```bash
pip install -r requirements.txt pytest
pytest
```

## License

MIT
