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
- **Discover** – paste any job description to check it against your CV before applying, then save it to a
  shortlist ranked by fit (with deadlines feeding into today's priorities) or add it as an application.
- **CV fit analysis** – for every job: essential vs. preferred requirements, evidence quoted from your CV,
  strengths, gaps, potential blockers (language, work permit, location, degree, experience) and a recommendation:
  *Apply*, *Apply with caveats* or *Deprioritise*.
- **Evidence bank** – your CV is split once into structured records (achievements, responsibilities,
  qualifications, projects) with their role, metrics, tools and stakeholders. Confirm records, add what you
  actually did, hide what's irrelevant, or add evidence that isn't on your CV.
- **CV builder** – a recruiter-style review per job: what the role prioritises, which of your lines to emphasise
  or reword, critiques of specific bullets (why it's weak + one concrete fix), questions a recruiter would ask,
  what to add if true, what to shorten, and keywords.
- **Cover letter builder** – the strongest experience-to-role connection, the most credible reason to be
  interested, the one example worth highlighting, what's missing from the story, generic statements to avoid,
  and a suggested structure. Both builders have a **Copy brief** button: a ready-made prompt to paste into any
  chat assistant to draft your own version.
- **Career development** – an **interview journal** (questions asked, how each answer went, what was hard, feedback,
  next steps) that surfaces **recurring themes**: question types you get most, where your answers are weakest, questions
  that keep coming back, and skills you're asked about but have no story for. A **personalised practice plan** built
  from your own interviews, your next interviews (what that company asked before, its essential requirements) and your
  weak spots, with instant STAR feedback on written answers. A **story bank** of reusable STAR examples, seeded from
  your evidence bank and matched to practice questions. A **skills report** across every job description you've saved
  or applied to (most requested, gaps, what's asked for more lately, essentials you were missing). And **industry
  notes**, shown next to your results in each industry.
- **Quick add** – press **N** anywhere, paste a job description, and title, company, seniority, industry, work
  permit, language, work mode and skills are filled in. Uncertain values are highlighted for review.
- **Consistent filters** – job family, industry, seniority, location, channel and date range apply to the board,
  the table, the insights and every chart.

Everything runs on your machine. Your data lives in a local SQLite file that is never committed.

## Local AI with Ollama (optional)

The fit analysis works out of the box with keyword matching. For analyses that read postings the way a person
would, and for recruiter-style CV and cover letter reviews, run a local model with [Ollama](https://ollama.com):

```bash
# install Ollama from https://ollama.com/download, then:
ollama pull qwen2.5:7b      # ~4.7 GB, good on 16 GB RAM (use qwen2.5:3b on 8 GB)
```

Then open **Settings → Profile, CV & AI**, click *Test connection*, pick the model and click *Measure speed*. Nothing
leaves your computer.

A 7B model on a laptop CPU writes roughly 4–10 tokens a second, so AI tasks take minutes, not seconds. They therefore
run **in the background, one at a time** (Ollama answers one request at a time anyway): you see live progress and a
time estimate, the sidebar shows what's running, you can keep working or stop a task, and reviews you ask for jump
ahead of batch ranking. CV and cover letter reviews come in two parts; the first part appears as soon as it's ready.
If your computer is slow, `qwen2.5:3b` is about twice as fast.

AI is optional everywhere: fit scores, CV and cover letter reviews, practice plans and answer feedback all have an
instant rule-based version, and each AI section is labelled so you know which one you're looking at.

The model is never trusted blindly: every piece of evidence it quotes is checked against your CV, and anything it
can't back up is downgraded (a "met" requirement becomes "partial"; a "backed" CV line becomes "needs your input").
The score and recommendation are computed by the app from the requirement statuses and the rule-based blockers,
so AI and keyword analyses are judged the same way.

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
around, or import your own spreadsheet there. Then, under **Settings → Profile, CV & AI**, upload your CV (PDF,
Word or text) and fill in your languages, degree, experience and work-permit status per location.

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
  fit.py            CV-vs-job analysis and blockers (keywords or Ollama)
  evidence.py       evidence bank: CV -> structured records (one-time), optional AI enrichment
  builder.py        job priorities, CV builder and cover letter builder (rules or focused Ollama review)
  career.py         interview journal themes, practice plan, answer feedback, story bank, skills report
  aijobs.py         background AI task queue (one at a time, priorities, progress, cancel)
  cvtext.py         CV text extraction (PDF, Word, text)
  llm.py            minimal Ollama client (streaming, speed measurement, truncated-JSON repair)
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
