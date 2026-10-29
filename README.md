# Job Tracker

A private, local job-application tracker that tells you **which kinds of roles you actually succeed in** — and
what to do today.

- **Add a job** – press **N** anywhere (or use the browser bookmark) and paste the whole posting page. Page clutter
  (buttons, "Apply", AI summaries, company boilerplate) is removed with one-click undo; position, company, location,
  workload, contract and deadline are filled in, with uncertain guesses highlighted; and an instant **fit check**
  shows the verdict and its reasons before you save. Save it for later or as an application.
- **Inbox** – everything you collect lands here first, as many as you like. Rank them all with your chat assistant,
  then mark each one **Applied** (it joins the board and the statistics) or **Skip** (kept out of the way under
  *Skipped*, and pasting the same posting again warns you). Only jobs you applied to count in Analytics.
- **Applications** – a drag-and-drop board (Applied onwards) and a sortable table with batch actions. Filter by
  current status or by the furthest stage reached ("an interview or later"). Every job opens in one panel whose
  first tab is **Prepare**: fit → apply → interview prep → journal.
- **Explainable fit** – rules only, instant: essential vs. preferred requirements (benefits and company text are
  ignored), the line in your profile that shows each one, blockers (language, permit, degree, experience) and a
  recommendation: *Apply*, *Apply with caveats* or *Deprioritise*. Soft skills are listed separately, not scored.
  Postings in German get the eligibility check only and are marked *Not scored*.
- **Your chat assistant does the thinking** – **Rank with chat assistant** copies a prompt with your profile and every
  Inbox job that isn't ranked yet (or the ones you tick); a long list is cut into parts of up to 30 jobs that the
  assistant can answer one at a time. Paste each reply back and every job gets its score, verdict, reason and your
  extra fields. Tomorrow's batch only contains the new jobs. Each job also has ready-made prompts: biggest weakness, which claim needs evidence,
  what would make a recruiter hesitate, tailor my CV, draft my cover letter, prepare me for the interview.
- **Me** – your profile as **entries** (experience, education, projects, publications, skills) instead of a CV file.
  Paste a CV section to split it into entries, or import your CV once and tidy the result. Plus eligibility and
  skills, the story bank and how you write.
- **Overview** – greeting, weekly goal ring and streak, today's priorities (follow-ups, likely ghosts, deadlines,
  reminders, thank-you notes), a momentum calendar, milestones and what's coming up.
- **Analytics** – conversion between every step, a funnel, **What works for you** (success rate by job family,
  seniority, industry, location, channel, timing…), monthly outcomes, a **Companies** tab (who replies, how fast,
  the ghost list) and a zoomable **map** (towns, plus countries when no town is given).
- **Career development** – interview journal with recurring themes, a practice plan with instant feedback (and a
  prompt to get deeper feedback from your chat assistant), story bank, skills report and industry notes.
- **Ctrl+K command bar**, **dark mode**, and undo for stage changes.

Everything runs on your machine. Your data lives in a local SQLite file that is never committed.

## Customising chat rankings

What your chat assistant fills in for each job is defined in **`config/ranking.yaml`** (also editable in
**Settings → Rules → Chat ranking fields**). By default it asks for an ATS match, interview chance, salary estimate,
competitiveness, top strengths and growth potential, on top of the built-in score, verdict, reason and main gap.
Add, remove or reword fields there; the prompt, the reply reader, the board cards and the job panel all follow, with
no code changes. Each field has a `type` (number, choice or text), an `ask` (the instruction to the assistant) and
`show: card` (chip on the board) or `show: detail` (job panel only).

Your own criteria ("prefer Switzerland, salary above 40k, German up to B1…") go in the box in the ranking window.
They're saved in your private database, not in the config file, so nothing personal gets committed.

## Ollama (optional): reading descriptions in the background

The tracker needs no AI. If you run [Ollama](https://ollama.com), a local model can read your saved job
descriptions in the background, once each, to pick out skills, industry and seniority that keyword rules miss.
This feeds the skills report and shows **where you get interviews by industry and seniority**.

```bash
# install Ollama from https://ollama.com/download, then:
ollama pull qwen2.5:7b      # ~4.7 GB, good on 16 GB RAM (use qwen2.5:3b on 8 GB)
```

In **Settings**, test the connection, measure speed and click *Read … with Ollama*; optionally turn on reading new
descriptions automatically. On a laptop each description takes roughly 30–50 seconds, so ~150 descriptions take
1–2 hours the first time (you can keep working or stop it) and under a minute per new job afterwards. Results are
cached by the description's content; the statistics themselves are instant.

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
around, or import your own spreadsheet there. Then, under **Me**, add your experience (or import your CV once)
and fill in your languages, degree, experience and work-permit status per location.

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
  posting.py        cleaning pasted postings and pulling out position, company, location, workload, contract, deadline
  fit.py            explainable rule-based fit and blockers
  entries.py        your profile as entries: paste-to-split, one-time CV conversion, evidence lines
  prompts.py        prompts for your chat assistant, reading its rankings back, config/ranking.yaml fields
  digest.py         optional background reading of descriptions with Ollama
  evidence.py       evidence lines used for matching
  builder.py        job priorities and evidence ranking
  career.py         interview journal themes, practice plan, answer feedback, story bank, skills report
  fun.py            momentum calendar, milestones, company reply times, map points (offline GeoNames towns)
  aijobs.py         background Ollama task queue (one at a time, priorities, progress, cancel)
  cvtext.py         CV text extraction (PDF, Word, text)
  llm.py            minimal Ollama client (streaming, speed measurement, truncated-JSON repair)
  dimensions.py     seniority / industry / permit / language / skills inference
  categorise.py     job family / location rules
  importer.py       Excel/CSV import and export
  web/              built interface (generated, committed so users don't need Node)
frontend/           React + TypeScript + Tailwind source
config/             editable rules (categories.yaml, dimensions.yaml, places.yaml for the map)
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
