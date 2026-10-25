"""Today's priorities: follow-ups, likely-ghosted applications, due reminders and upcoming interviews."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd

from .storage import Store

INTERVIEW_STAGES = {"Interview", "Final interview"}


def build(store: Store, df: pd.DataFrame, settings: dict, today: date | None = None) -> list[dict]:
    """Return the open priority items, most urgent first.

    Each item: {key, kind, severity, title, detail, application_id, due, actions}.
    `key` is stable for the underlying situation so snoozing/dismissing sticks until something changes.
    """
    today = today or date.today()
    state = store.notification_state()
    items: list[dict] = []

    def hidden(key: str) -> bool:
        s = state.get(key)
        if not s:
            return False
        if s["dismissed"]:
            return True
        return bool(s["snoozed_until"]) and pd.Timestamp(s["snoozed_until"]).date() > today

    fu_after = int(settings.get("follow_up_after", 10))
    ghost_after = int(settings.get("ghost_after", 42))

    # Reminders that are due (or overdue).
    rem = store.reminders()
    for r in rem.itertuples():
        due = r.due_date.date()
        if due > today + timedelta(days=0):
            continue
        key = f"reminder:{r.id}"
        if hidden(key):
            continue
        overdue = (today - due).days
        items.append({
            "key": key, "kind": "reminder", "severity": "high" if overdue > 0 else "medium",
            "title": r.title,
            "detail": (f"{r.company} · {r.position}. " if isinstance(r.company, str) else "")
            + ("Due today" if overdue == 0 else f"Overdue by {overdue} day{'s' if overdue != 1 else ''}"),
            "application_id": None if pd.isna(r.application_id) else int(r.application_id),
            "reminder_id": int(r.id), "due": due.isoformat(), "actions": ["done", "snooze"],
        })

    if not df.empty:
        ev = store.events()
        # Upcoming interviews (next 14 days) and thank-you notes after recent interviews.
        upcoming = ev[ev["stage"].isin(INTERVIEW_STAGES) & (ev["date"].dt.date >= today)
                      & (ev["date"].dt.date <= today + timedelta(days=14))]
        names = df.set_index("id")[["company", "position", "status"]]
        for e in upcoming.itertuples():
            if e.application_id not in names.index:
                continue
            a = names.loc[e.application_id]
            days = (e.date.date() - today).days
            key = f"interview:{e.id}"
            if hidden(key):
                continue
            items.append({
                "key": key, "kind": "interview", "severity": "high" if days <= 1 else "medium",
                "title": f"{e.stage} with {a['company']}",
                "detail": f"{a['position']} · " + ("today" if days == 0 else "tomorrow" if days == 1 else f"in {days} days")
                + (f" · {e.note}" if isinstance(e.note, str) and e.note else ""),
                "application_id": int(e.application_id), "due": e.date.date().isoformat(),
                "actions": ["open", "snooze"],
            })
        recent = ev[ev["stage"].isin(INTERVIEW_STAGES) & (ev["date"].dt.date < today)
                    & (ev["date"].dt.date >= today - timedelta(days=2))]
        for e in recent.itertuples():
            if e.application_id not in names.index:
                continue
            a = names.loc[e.application_id]
            key = f"thanks:{e.id}"
            if hidden(key) or a["status"] not in INTERVIEW_STAGES:
                continue
            items.append({
                "key": key, "kind": "thank_you", "severity": "medium",
                "title": f"Send a thank-you note to {a['company']}",
                "detail": f"After your {e.stage.lower()} on {e.date:%d %b}. Also a good moment to log it in your journal.",
                "application_id": int(e.application_id), "due": today.isoformat(), "actions": ["done", "snooze"],
            })

        active = df[df["status"].isin(["Applied", "Screening", "Interview", "Final interview"])]
        for r in active.itertuples():
            idle = int(r.days_since_activity)
            last = r.last_activity.date().isoformat()
            # Skip applications with an interview still coming up.
            if r.status in INTERVIEW_STAGES and r.last_activity.date() >= today:
                continue
            if r.status == "Applied" and idle >= ghost_after:
                key = f"ghost:{r.id}:{last}"
                if not hidden(key):
                    items.append({
                        "key": key, "kind": "ghost", "severity": "low",
                        "title": f"No reply from {r.company} in {idle} days",
                        "detail": f"{r.position}. Mark it as ghosted to keep your pipeline accurate.",
                        "application_id": int(r.id), "due": today.isoformat(), "idle": idle,
                        "actions": ["mark_ghosted", "snooze", "dismiss"],
                    })
            elif idle >= fu_after:
                key = f"followup:{r.id}:{last}"
                if not hidden(key):
                    items.append({
                        "key": key, "kind": "follow_up", "severity": "medium" if r.status != "Applied" else "low",
                        "title": f"Follow up with {r.company}",
                        "detail": f"{r.position} · {r.status} · {idle} days without news",
                        "application_id": int(r.id), "due": today.isoformat(), "idle": idle,
                        "actions": ["followed_up", "snooze", "dismiss"],
                    })

    order = {"high": 0, "medium": 1, "low": 2}
    kind_order = {"interview": 0, "reminder": 1, "thank_you": 2, "follow_up": 3, "ghost": 4}
    items.sort(key=lambda i: (order[i["severity"]], kind_order[i["kind"]], i["due"], -i.get("idle", 0)))
    return items
