"""Job Search & Resume Matcher — Streamlit app."""
from datetime import datetime

import pandas as pd
import streamlit as st

import analyzer
import job_search as js
import tracker as trk
from config import (
    DATE_FILTER_OPTIONS,
    EMPLOYMENT_TYPES,
    STAR_LABELS,
    STATUS_OPTIONS,
    get_anthropic_key,
    get_google_credentials_path,
    get_rapidapi_key,
    get_serpapi_key,
)
from resume_parser import parse_resume

st.set_page_config(
    page_title="Job Search & Resume Matcher",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Session state defaults ────────────────────────────────────────────────────
_defaults = {
    "resume_text": "",
    "jobs_raw": [],
    "jobs_scored": [],
    "search_done": False,
    "tailored": {},   # job_id -> tailored text
    "tracker_df": None,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ── Sidebar: Profile & API Keys ───────────────────────────────────────────────
with st.sidebar:
    st.title("🔍 Job Search Tool")
    st.markdown("---")

    # --- Resume upload
    st.subheader("📄 Your Resume")
    upload = st.file_uploader(
        "Upload resume (PDF, DOCX, or TXT)",
        type=["pdf", "docx", "txt", "md"],
        help="Your resume is parsed locally — never sent anywhere except your chosen AI provider.",
    )
    if upload:
        text = parse_resume(upload)
        if text and not text.startswith("["):
            st.session_state["resume_text"] = text
            st.success(f"Parsed — {len(text):,} characters")
        else:
            st.error(f"Could not parse: {text}")

    if not st.session_state["resume_text"]:
        manual = st.text_area(
            "…or paste resume text",
            height=180,
            placeholder="Paste your full resume here",
        )
        if manual.strip():
            st.session_state["resume_text"] = manual.strip()

    # --- Sponsorship toggle
    st.markdown("---")
    st.subheader("🌍 Work Authorization")
    require_sponsorship = st.toggle(
        "I need visa sponsorship",
        value=False,
        help="Adds 'visa sponsorship' to the search query and filters results to confirmed-sponsorship roles.",
    )

    # --- API Keys (collapsible)
    st.markdown("---")
    with st.expander("🔑 API Keys", expanded=False):
        st.caption("Keys set via Streamlit Secrets or .env are used automatically and never displayed.")

        _env_anthropic = get_anthropic_key()
        _env_rapid = get_rapidapi_key()
        _env_serp = get_serpapi_key()

        if _env_anthropic:
            st.success("Anthropic API Key: ✅ Configured via Secrets")
            anthropic_key = ""
        else:
            anthropic_key = st.text_input(
                "Anthropic API Key", value="",
                type="password", key="anthropic_key_input",
                placeholder="sk-ant-...",
            )

        if _env_rapid:
            st.success("RapidAPI Key (JSearch): ✅ Configured via Secrets")
            rapidapi_key = ""
        else:
            rapidapi_key = st.text_input(
                "RapidAPI Key (JSearch)", value="",
                type="password", key="rapidapi_key_input",
                placeholder="Paste your RapidAPI key",
            )

        if _env_serp:
            st.success("SerpAPI Key: ✅ Configured via Secrets")
            serpapi_key = ""
        else:
            serpapi_key = st.text_input(
                "SerpAPI Key (fallback)", value="",
                type="password", key="serpapi_key_input",
                placeholder="Paste your SerpAPI key",
            )

        st.markdown(
            "[Get JSearch key](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) · "
            "[Get SerpAPI key](https://serpapi.com) · "
            "[Get Anthropic key](https://console.anthropic.com)"
        )

    # Secret values take priority; fall back to what user typed in the UI
    eff_anthropic = _env_anthropic or anthropic_key
    eff_rapid = _env_rapid or rapidapi_key
    eff_serp = _env_serp or serpapi_key


# ── Main Tabs ─────────────────────────────────────────────────────────────────
tab_search, tab_results, tab_tailor, tab_tracker = st.tabs(
    ["🔍 Search", "⭐ Results", "📄 Tailor Resume", "📊 Job Tracker"]
)


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 1 — Search
# ═══════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.header("Job Search")

    col1, col2 = st.columns([2, 1])
    with col1:
        job_query = st.text_input(
            "Job title / keywords",
            placeholder="e.g. Senior Python Engineer, ML Engineer, Product Manager",
        )
    with col2:
        location = st.text_input(
            "Location",
            placeholder="e.g. New York, UK, Remote, Germany",
        )

    col3, col4, col5, col6 = st.columns(4)
    with col3:
        date_label = st.selectbox("Date posted", list(DATE_FILTER_OPTIONS.keys()))
        date_value = DATE_FILTER_OPTIONS[date_label]
    with col4:
        emp_label = st.selectbox("Employment type", list(EMPLOYMENT_TYPES.keys()))
        emp_value = EMPLOYMENT_TYPES[emp_label]
    with col5:
        remote_only = st.checkbox("Remote only")
    with col6:
        num_pages = st.slider("Pages to fetch", 1, 5, 2,
                              help="Each page ≈ 10 jobs. More pages = more API calls.")

    # Sponsorship-specific country filter
    if require_sponsorship:
        st.info(
            "🌍 **Sponsorship mode ON** — search results will include 'visa sponsorship' as a keyword "
            "and Claude will confirm which JDs explicitly offer sponsorship."
        )

    search_ready = (
        bool(job_query.strip())
        and (bool(eff_rapid) or bool(eff_serp))
        and bool(eff_anthropic)
        and bool(st.session_state["resume_text"])
    )

    if not st.session_state["resume_text"]:
        st.warning("Upload or paste your resume in the sidebar before searching.")
    if not (eff_rapid or eff_serp):
        st.warning("Add at least one job search API key (RapidAPI or SerpAPI) in the sidebar.")
    if not eff_anthropic:
        st.warning("Add your Anthropic API key in the sidebar to enable fit analysis.")

    if st.button("🚀 Search & Analyze", disabled=not search_ready, type="primary"):
        with st.spinner("Searching for jobs…"):
            jobs_raw = js.search_jobs(
                query=job_query.strip(),
                location=location.strip(),
                date_posted=date_value,
                employment_type=emp_value,
                remote_only=remote_only,
                require_sponsorship=require_sponsorship,
                num_pages=num_pages,
                rapidapi_key=eff_rapid,
                serpapi_key=eff_serp,
            )

        if not jobs_raw:
            st.error("No jobs found. Try broadening your search or check your API keys.")
        else:
            st.success(f"Found {len(jobs_raw)} jobs. Analyzing fit with Claude…")
            with st.spinner(f"Scoring {len(jobs_raw)} jobs against your resume…"):
                scores = analyzer.score_jobs(
                    resume_text=st.session_state["resume_text"],
                    jobs=jobs_raw,
                    api_key=eff_anthropic,
                )
                jobs_scored = analyzer.merge_scores(jobs_raw, scores)

            # If sponsorship required, deep-check top candidates
            if require_sponsorship:
                top_ids = {j["id"] for j in jobs_scored if j.get("stars", 0) >= 4}
                with st.spinner("Verifying sponsorship for top matches…"):
                    for j in jobs_scored:
                        if j["id"] in top_ids:
                            result = analyzer.check_sponsorship_deep(j, eff_anthropic)
                            j["sponsorship_confirmed"] = result["confirmed_sponsorship"]
                            j["sponsorship_note"] = result.get("sponsorship_note", "")

            st.session_state["jobs_raw"] = jobs_raw
            st.session_state["jobs_scored"] = sorted(
                jobs_scored, key=lambda x: x.get("stars", 0), reverse=True
            )
            st.session_state["search_done"] = True
            st.success("✅ Analysis complete! Go to the **⭐ Results** tab.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 2 — Results
# ═══════════════════════════════════════════════════════════════════════════════
with tab_results:
    st.header("Job Match Results")

    if not st.session_state["search_done"] or not st.session_state["jobs_scored"]:
        st.info("Run a search first.")
    else:
        jobs = st.session_state["jobs_scored"]

        # ---- Filters
        fcol1, fcol2, fcol3 = st.columns(3)
        with fcol1:
            min_stars = st.selectbox(
                "Minimum stars", [1, 2, 3, 4, 5], index=0,
                format_func=lambda x: STAR_LABELS[x],
            )
        with fcol2:
            spons_filter = st.selectbox(
                "Sponsorship",
                ["All", "Confirmed sponsorship only", "Sponsorship mentioned", "No sponsorship needed"],
            )
        with fcol3:
            source_filter = st.multiselect(
                "Source", ["JSearch", "SerpAPI"],
                default=list({j["source"] for j in jobs}),
            )

        filtered = [j for j in jobs if j.get("stars", 0) >= min_stars]
        if spons_filter == "Confirmed sponsorship only":
            filtered = [j for j in filtered if j.get("sponsorship_confirmed")]
        elif spons_filter == "Sponsorship mentioned":
            filtered = [j for j in filtered if j.get("sponsorship_mentioned")]
        elif spons_filter == "No sponsorship needed":
            filtered = filtered  # show all
        if source_filter:
            filtered = [j for j in filtered if j.get("source") in source_filter]

        st.markdown(f"**Showing {len(filtered)} jobs** (filtered from {len(jobs)} total)")

        if not filtered:
            st.warning(
                "No jobs match the current filters. "
                "Try lowering the **Minimum stars** filter to ⭐ Weak Match to see all results."
            )

        # ---- Star summary counts
        star_counts = {}
        for j in jobs:
            s = j.get("stars", 0)
            star_counts[s] = star_counts.get(s, 0) + 1

        mcols = st.columns(5)
        for i, star in enumerate([5, 4, 3, 2, 1]):
            mcols[i].metric(STAR_LABELS[star], star_counts.get(star, 0))

        st.markdown("---")

        # ---- Job cards
        for job in filtered:
            stars = job.get("stars", 0)
            star_emoji = "⭐" * stars if stars else "—"
            sponsored_badge = ""
            if job.get("sponsorship_confirmed"):
                sponsored_badge = " 🟢 **Sponsorship confirmed**"
            elif job.get("sponsorship_mentioned"):
                sponsored_badge = " 🟡 Sponsorship mentioned"

            with st.expander(
                f"{star_emoji} **{job['title']}** @ {job['company']} · {job['location']}{sponsored_badge}",
                expanded=(stars >= 4),
            ):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"**Match Score:** {job.get('match_score', '?'):.0f}/100")
                    st.markdown(f"**Summary:** {job.get('fit_summary', '')}")
                    if job.get("why_apply"):
                        st.success(f"💡 {job['why_apply']}")

                    mskills = job.get("matched_skills", [])
                    missing = job.get("missing_skills", [])
                    if mskills:
                        st.markdown("**✅ Matched skills:** " + " · ".join(f"`{s}`" for s in mskills[:12]))
                    if missing:
                        st.markdown("**⚠️ Missing skills:** " + " · ".join(f"`{s}`" for s in missing[:8]))

                    if job.get("sponsorship_note"):
                        st.caption(f"Sponsorship note: {job['sponsorship_note']}")

                with col_b:
                    st.markdown(f"**Posted:** {job.get('date_posted', 'N/A')}")
                    st.markdown(f"**Type:** {job.get('employment_type', 'N/A')}")
                    st.markdown(f"**Source:** {job.get('source', '')}")
                    if job.get("apply_url"):
                        st.link_button("🔗 Apply Now", job["apply_url"])

                    # Tracker button
                    btn_key = f"save_{job['id']}"
                    if st.button("📌 Save to Tracker", key=btn_key):
                        ok = trk.save_application(job, status="Saved")
                        if ok:
                            st.success("Saved!")
                        else:
                            st.error("Save failed — check tracker config.")

                # JD preview
                with st.expander("📋 Job Description (preview)", expanded=False):
                    st.markdown(job.get("description", "")[:2000] + ("…" if len(job.get("description","")) > 2000 else ""))

                # Tailor button
                if stars >= 4 and st.session_state["resume_text"]:
                    tailor_key = f"tailor_{job['id']}"
                    if st.button(f"✍️ Tailor Resume for this role", key=tailor_key):
                        with st.spinner("Claude is tailoring your resume…"):
                            tailored = analyzer.tailor_resume(
                                resume_text=st.session_state["resume_text"],
                                job=job,
                                api_key=eff_anthropic,
                            )
                            st.session_state["tailored"][job["id"]] = {
                                "tailored": tailored,
                                "job": job,
                            }
                        st.success("✅ Done! Check the **📄 Tailor Resume** tab.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 3 — Tailor Resume
# ═══════════════════════════════════════════════════════════════════════════════
with tab_tailor:
    st.header("Tailored Resumes")

    if not st.session_state["tailored"]:
        st.info(
            "No tailored resumes yet. In the **⭐ Results** tab, click "
            "**✍️ Tailor Resume for this role** on any 4-star or 5-star job."
        )
    else:
        for jid, entry in st.session_state["tailored"].items():
            job = entry["job"]
            content = entry["tailored"]

            st.subheader(f"{job['title']} @ {job['company']}")
            st.caption(f"{job['location']} · {STAR_LABELS.get(job.get('stars', 0), '')}")

            if job.get("apply_url"):
                st.link_button("🔗 Apply Now", job["apply_url"])

            # Download button
            fname = f"resume_{job['company'].replace(' ','_')}_{job['title'].replace(' ','_')}.md"
            st.download_button(
                "⬇️ Download as Markdown",
                data=content.encode(),
                file_name=fname,
                mime="text/markdown",
                key=f"dl_{jid}",
            )

            st.markdown(content)
            st.markdown("---")

            # Save to tracker from here too
            if st.button(f"📌 Save {job['title']} @ {job['company']} to Tracker", key=f"tr_{jid}"):
                ok = trk.save_application(job, status="Saved", notes="Resume tailored")
                st.success("Saved to tracker!" if ok else "Save failed.")


# ═══════════════════════════════════════════════════════════════════════════════
# TAB 4 — Job Tracker
# ═══════════════════════════════════════════════════════════════════════════════
with tab_tracker:
    st.header("Job Application Tracker")

    if st.button("🔄 Refresh tracker", key="refresh_tracker"):
        st.session_state["tracker_df"] = None

    if st.session_state["tracker_df"] is None:
        st.session_state["tracker_df"] = trk.load_tracker()

    df = st.session_state["tracker_df"]

    if df.empty:
        st.info("No applications tracked yet. Save jobs from the Results or Tailor Resume tabs.")
    else:
        # ---- Summary metrics
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total saved", len(df))
        m2.metric("Applied", len(df[df["Status"] == "Applied"]))
        m3.metric("Interviewing", len(df[df["Status"].isin(["Phone Screen", "Interview"])]))
        m4.metric("Offers", len(df[df["Status"] == "Offer"]))
        m5.metric("⭐ 5-star roles", len(df[df["Star Rating"] == "5"]))

        st.markdown("---")

        # ---- Editable table
        st.subheader("Applications")
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            num_rows="dynamic",
            column_config={
                "Apply URL": st.column_config.LinkColumn("Apply URL"),
                "Status": st.column_config.SelectboxColumn("Status", options=STATUS_OPTIONS),
                "Star Rating": st.column_config.NumberColumn("⭐ Stars", min_value=1, max_value=5),
                "Date Added": st.column_config.DateColumn("Date Added"),
                "Date Applied": st.column_config.DateColumn("Date Applied"),
            },
            key="tracker_editor",
        )

        col_save, col_dl = st.columns(2)
        with col_save:
            if st.button("💾 Save changes", type="primary"):
                ok = trk._save_df(edited_df)
                if ok:
                    st.session_state["tracker_df"] = edited_df
                    st.success("Saved!")
                else:
                    st.error("Save failed.")
        with col_dl:
            csv_bytes = trk.export_csv(edited_df)
            st.download_button(
                "⬇️ Export CSV",
                data=csv_bytes,
                file_name=f"job_tracker_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv",
            )

        # ---- Status breakdown chart
        if not df.empty and "Status" in df.columns:
            st.markdown("---")
            st.subheader("Application Pipeline")
            status_counts = df["Status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            st.bar_chart(status_counts.set_index("Status"))

        # ---- Google Sheets link
        goog_creds = get_google_credentials_path()
        if goog_creds:
            st.caption("✅ Google Sheets sync enabled — changes are saved to your spreadsheet.")
        else:
            st.caption(
                "📁 Saving to local `job_tracker.csv`. "
                "To sync with Google Sheets, set `GOOGLE_CREDENTIALS_JSON` in your `.env` file."
            )
