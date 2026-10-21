"""Generate fictional sample applications so the repo can be explored without real data.

The numbers are made up but follow plausible patterns (referrals and early applications do
better, roles requiring fluent German do worse) so every chart has something to show.

Run:  python sample_data/generate_sample.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(11)

# Fictional companies: name -> (industry, size)
COMPANIES = {
    "Alpenwell Pharma": ("Pharma / biotech", "Large (1000+)"),
    "Rhinebridge Bio": ("Pharma / biotech", "SME (50–999)"),
    "Nordhaven CRO": ("CRO / clinical services", "Large (1000+)"),
    "Orchid Clinical": ("CRO / clinical services", "SME (50–999)"),
    "Kestrel Devices": ("Medtech / diagnostics", "SME (50–999)"),
    "Quayside Medical": ("Medtech / diagnostics", "Large (1000+)"),
    "Sundial AI": ("Technology / AI", "Startup (<50)"),
    "Lakeside Analytics": ("Health tech / digital health", "Startup (<50)"),
    "Corvina Health": ("Health tech / digital health", "SME (50–999)"),
    "Bluepeak Consulting": ("Consulting", "Large (1000+)"),
    "Tessellate Partners": ("Consulting", "SME (50–999)"),
    "Helix & Hart": ("Publishing / media", "SME (50–999)"),
}
# title -> (base chance of a positive reply, skills mentioned)
ROLES = {
    "Clinical Trial Assistant": (0.05, ["GCP", "clinical trials", "eTMF", "Excel"]),
    "Clinical Research Associate": (0.04, ["ICH-GCP", "monitoring", "site management", "clinical trials"]),
    "Junior Clinical Data Manager": (0.08, ["EDC", "SQL", "CDISC", "clinical trials"]),
    "Data Scientist": (0.07, ["Python", "machine learning", "SQL", "statistics", "cloud"]),
    "Junior Data Analyst": (0.12, ["Python", "R", "SQL", "Tableau", "statistics"]),
    "Machine Learning Engineer": (0.04, ["Python", "PyTorch", "Docker", "machine learning", "AWS"]),
    "Neuroimaging Data Scientist": (0.20, ["Python", "MRI", "fMRI", "neuroimaging", "statistics", "R"]),
    "Graduate Programme - R&D": (0.12, ["project management", "statistics", "presentation skills"]),
    "Commercial Trainee": (0.07, ["marketing", "stakeholder management", "Excel"]),
    "Regulatory Affairs Associate": (0.06, ["regulatory affairs", "GxP", "medical writing"]),
    "Medical Writer": (0.08, ["medical writing", "clinical trials", "statistics"]),
    "Associate Consultant - Life Sciences": (0.10, ["consulting", "Excel", "market access", "stakeholder management"]),
    "Senior Biostatistician": (0.02, ["R", "SAS", "biostatistics", "CDISC"]),
    "Research Associate - Real World Evidence": (0.10, ["epidemiology", "R", "real world evidence", "statistics"]),
}
LOCATIONS = ["Zurich", "Basel", "Geneva", "Zug", "London", "Munich", "Berlin", "Amsterdam", "Remote", "Milan"]
SOURCES = ["LinkedIn", "Company website", "Job portal", "Referral", "Recruiter", "Cold email"]
SOURCE_BOOST = {"Referral": 3.0, "Recruiter": 1.6, "Cold email": 0.6}
CVS = ["General v1", "Data science v2", "Clinical v2"]


def job_description(company, role, skills, years, german, permit, mode):
    parts = [f"{company} is looking for a {role} to join our team.",
             "Responsibilities include working with cross-functional teams and delivering high quality results.",
             f"Requirements: {years}+ years of relevant experience; experience with {', '.join(skills)}.",
             "Excellent English communication skills."]
    if german == "req":
        parts.append("Fluent German is required.")
    elif german == "plus":
        parts.append("German is a plus.")
    if permit == "need":
        parts.append("Candidates must hold a valid work permit for this country.")
    elif permit == "sponsor":
        parts.append("We offer visa sponsorship and relocation support.")
    parts.append({"hybrid": "Hybrid working with two home office days.", "remote": "This is a fully remote position.",
                  "onsite": "This role is on-site at our headquarters."}[mode])
    return " ".join(parts)


rows = []
start, today = date(2026, 2, 1), date(2026, 10, 16)
for _ in range(180):
    company, (industry, size) = random.choice(list(COMPANIES.items()))
    role, (p, skills) = random.choice(list(ROLES.items()))
    src = random.choice(SOURCES)
    applied = start + timedelta(days=int(random.triangular(0, (today - start).days, 200)))
    lag = random.choice([0, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45])
    posted = applied - timedelta(days=lag)
    loc = random.choice(LOCATIONS)
    german = random.choices(["none", "plus", "req"], [5, 3, 2])[0]
    permit = random.choices(["none", "need", "sponsor"], [6, 3, 1])[0]
    mode = "remote" if loc == "Remote" else random.choice(["hybrid", "hybrid", "onsite"])
    years = 0 if "Graduate" in role or "Trainee" in role or "Junior" in role else random.choice([1, 2, 3, 5])
    fit = random.choice([2, 3, 3, 4, 4, 5])

    p *= SOURCE_BOOST.get(src, 1.0)
    p *= 1.6 if lag <= 3 else 0.6 if lag >= 21 else 1.0
    p *= 0.3 if german == "req" else 1.0
    p *= 0.5 if permit == "need" else 1.0
    p *= 0.5 + fit / 5
    p = min(0.7, p)

    age = (today - applied).days
    r = random.random()
    if age < 21:
        status, final = "Submitted", ""
    elif r < p:
        status = "Interview"
        final = random.choice(["Rejected", "Rejected", "Offer", ""]) if age > 40 else ""
    elif r < p + 0.45:
        status, final = "Rejected", ""
    else:
        status, final = ("Ghosted", "") if age > 42 else ("Submitted", "")
    rows.append({
        "Company": company, "Position": role, "Date Posted": posted.isoformat(), "Date Applied": applied.isoformat(),
        "Application Status": status, "Final Status": final, "Location": loc, "Source": src,
        "Industry": industry, "Company Size": size, "CV Version": random.choice(CVS), "Fit": fit,
        "Job Description": job_description(company, role, skills, years, german, permit, mode), "Notes": "",
    })

out = Path(__file__).with_name("sample_applications.csv")
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: r["Date Applied"]))
print(f"Wrote {len(rows)} rows to {out}")
