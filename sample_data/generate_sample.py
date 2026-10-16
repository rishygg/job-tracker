"""Generate fictional sample applications so the repo can be explored without real data.

Run:  python sample_data/generate_sample.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

random.seed(7)

COMPANIES = ["Alpenwell Pharma", "Rhinebridge Bio", "Lakeside Analytics", "Nordhaven CRO", "Helix & Hart",
             "Corvina Health", "Bluepeak Consulting", "Mettler Ridge Labs", "Quayside Medical", "Sundial AI",
             "Vireo Therapeutics", "Granite Data Co", "Orchid Clinical", "Tessellate Partners", "Kestrel Devices"]
ROLES = {
    "Clinical Trial Assistant": 0.03, "Clinical Research Associate": 0.04, "Clinical Data Manager": 0.05,
    "Data Scientist": 0.08, "Junior Data Analyst": 0.10, "Machine Learning Engineer": 0.05,
    "Graduate Programme - R&D": 0.12, "Commercial Trainee": 0.08,
    "Regulatory Affairs Associate": 0.06, "Medical Writer": 0.07,
    "Associate Consultant - Life Sciences": 0.09, "Business Analyst": 0.07,
    "Brand Marketing Associate": 0.04, "Research Associate": 0.10,
}
LOCATIONS = ["Zurich", "Basel", "Geneva", "Zug", "London", "Munich", "Berlin", "Amsterdam", "Remote", "Milan"]
SOURCES = ["LinkedIn", "Company website", "Job portal", "Referral", "Recruiter", "Cold email"]
SOURCE_BOOST = {"Referral": 3.0, "Recruiter": 1.6, "Cold email": 0.6}

rows = []
start = date(2026, 2, 1)
today = date(2026, 10, 16)
for i in range(160):
    role, p_int = random.choice(list(ROLES.items()))
    src = random.choice(SOURCES)
    applied = start + timedelta(days=int(random.triangular(0, (today - start).days, 200)))
    age = (today - applied).days
    p = min(0.6, p_int * SOURCE_BOOST.get(src, 1.0))
    r = random.random()
    if age < 21:
        status, final = "Submitted", ""
    elif r < p:
        status = "Interview"
        final = random.choice(["Rejected", "Rejected", "Offer", ""]) if age > 40 else ""
    elif r < p + 0.5:
        status, final = "Rejected", ""
    else:
        status, final = ("Ghosted", "") if age > 42 else ("Submitted", "")
    rows.append({
        "Company": random.choice(COMPANIES), "Position": role, "Date Applied": applied.isoformat(),
        "Application Status": status, "Final Status": final, "Location": random.choice(LOCATIONS),
        "Source": src, "Notes": "",
    })

out = Path(__file__).with_name("sample_applications.csv")
with open(out, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=list(rows[0]))
    w.writeheader()
    w.writerows(sorted(rows, key=lambda r: r["Date Applied"]))
print(f"Wrote {len(rows)} rows to {out}")
