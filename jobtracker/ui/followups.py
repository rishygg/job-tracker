"""Follow-ups: applications that have gone quiet."""

from __future__ import annotations

from datetime import date

import streamlit as st

from jobtracker import analysis as A

from .common import Ctx, txt


def page(ctx: Ctx) -> None:
    st.title("Follow-ups")
    fu_after, ghost_after = int(ctx.settings["follow_up_after"]), int(ctx.settings["ghost_after"])
    st.caption(f"Open applications with no activity for {fu_after}+ days. Ones with no reply after {ghost_after}+ "
               "days are suggested as ghosted. Change these limits in Settings.")
    fu = A.follow_ups(ctx.df, fu_after, ghost_after)
    if fu.empty:
        st.success("Nothing to chase right now.")
        return
    store = ctx.store
    for title, part in [("Worth a follow-up", fu[fu["action"] == "Follow up"]),
                        ("Probably ghosted", fu[fu["action"] == "Mark as ghosted"])]:
        if part.empty:
            continue
        c1, c2 = st.columns([3, 1])
        c1.subheader(f"{title} ({len(part)})")
        if title == "Probably ghosted" and c2.button(f"Mark all {len(part)} as ghosted"):
            for i in part["id"]:
                store.move_stage(int(i), "Ghosted", date.today(), "No reply")
            st.rerun()
        for _, r in part.iterrows():
            c1, c2, c3, c4 = st.columns([4, 1.2, 1.2, 1.2])
            contact = txt(r["contact"])
            c1.markdown(f"**{r['company']}** · {r['position']}  \n"
                        f"<small>{r['status']} · {int(r['days_since_activity'])} days idle"
                        f"{' · ' + contact if contact else ''}</small>", unsafe_allow_html=True)
            if c2.button("Followed up", key=f"fu-{r['id']}"):
                store.move_stage(int(r["id"]), r["status"], date.today(), "Followed up")
                st.rerun()
            if c3.button("Rejected", key=f"rj-{r['id']}"):
                store.move_stage(int(r["id"]), "Rejected", date.today())
                st.rerun()
            if c4.button("Ghosted", key=f"gh-{r['id']}"):
                store.move_stage(int(r["id"]), "Ghosted", date.today())
                st.rerun()
