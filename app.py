# app.py
# Streamlit advisor UI for Waypoint
# Run: streamlit run app.py

import streamlit as st
from waypoint.agent import run_waypoint
from waypoint.db import get_all_flags
from waypoint.llm import generate_outreach_message
from config import CSV_PATH, validate_config

# ── Page Config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Waypoint",
    page_icon="🧭",
    layout="wide",
)

# ── Config Sanity Check ───────────────────────────────────────────────────────
for warning in validate_config():
    st.warning(f"⚠️ Configuration: {warning}")

# ── Styles ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .flag-card {
        background-color: #f8f9fa;
        border-left: 4px solid #3D5A80;
        padding: 1rem 1.2rem;
        border-radius: 4px;
        margin-bottom: 1rem;
    }
    .flag-card-llm {
        border-left-color: #6B4E9B;
    }
    .flag-card-error {
        border-left-color: #B23A48;
        background-color: #fdf2f2;
    }
</style>
""", unsafe_allow_html=True)

# ── Session State ─────────────────────────────────────────────────────────────
if "pipeline_run" not in st.session_state:
    st.session_state.pipeline_run = False
if "decisions" not in st.session_state:
    st.session_state.decisions = {}
if "outreach_messages" not in st.session_state:
    st.session_state.outreach_messages = {}
if "confirm_rerun" not in st.session_state:
    st.session_state.confirm_rerun = False


def run_pipeline():
    with st.spinner("Running Waypoint pipeline... this may take 30 to 60 seconds while Claude evaluates ambiguous cases."):
        state = run_waypoint(CSV_PATH)
        st.session_state.pipeline_state = state
        st.session_state.pipeline_run = True
        st.session_state.decisions = {}
        st.session_state.outreach_messages = {}


def render_footer():
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.markdown("**Waypoint** — Student Success Nudge Agent")
    col2.markdown("Built by [AnneAble Consulting](https://www.anneable.com/)")
    col3.markdown("[GitHub Repository](https://github.com/aduperault/waypoint)")
    col4.markdown("Requires an [Anthropic API key](https://www.anthropic.com/pricing) to run locally")
    st.caption("Proof of concept — not tested with real student data.")


# ── Header ────────────────────────────────────────────────────────────────────
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🧭 Waypoint")
    st.caption("Student Success Nudge Agent — Redrock College (Demo)")
with col2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("▶ Run Demo", type="primary", use_container_width=True, key="run_top"):
        if st.session_state.pipeline_run and st.session_state.decisions:
            # Re-running wipes the database and resets all review state.
            # Don't do that silently if the advisor has unreviewed work.
            st.session_state.confirm_rerun = True
        else:
            run_pipeline()
        st.rerun()

if st.session_state.confirm_rerun:
    confirmed_count = sum(1 for d in st.session_state.decisions.values() if d == "confirmed")
    dismissed_count = sum(1 for d in st.session_state.decisions.values() if d == "dismissed")
    st.warning(
        f"You've reviewed {confirmed_count + dismissed_count} flag(s) this run "
        f"({confirmed_count} confirmed, {dismissed_count} dismissed). Running again "
        f"will reload from the CSV and **discard this review** — it cannot be undone."
    )
    cc1, cc2, _ = st.columns([2, 1, 4])
    with cc1:
        if st.button("Yes, run again and discard my review", type="primary", key="confirm_rerun_yes"):
            st.session_state.confirm_rerun = False
            run_pipeline()
            st.rerun()
    with cc2:
        if st.button("Cancel", key="confirm_rerun_cancel"):
            st.session_state.confirm_rerun = False
            st.rerun()

st.markdown("---")

# ── About Waypoint ────────────────────────────────────────────────────────────
with st.expander("About Waypoint", expanded=not st.session_state.pipeline_run):
    st.markdown("""
**Waypoint** is a proof-of-concept AI-powered student success agent, designed to demonstrate
how higher education institutions with limited resources, siloed systems, and connectivity
constraints can begin to leverage AI — the "crawl" stage in a crawl → walk → run adoption
framework.

Unlike solutions that require CRM integration or cloud-connected education platforms, Waypoint
operates from a single CSV export, the kind any institution can generate from a basic SIS.
No platform integration is required to operate this agent.

Waypoint applies a two-tier approach: deterministic rules handle clear cases instantly, and
Anthropic Claude evaluates ambiguous ones with nuanced reasoning. The batch architecture is
intentional: it minimizes token usage, processing overhead, and API dependency, making it
viable even in low-connectivity environments.

In this demo, Waypoint analyzes student credit completion data and surfaces two types of
advisor nudges: students who are **one course away** from a credential milestone, and students
building **credit momentum** who have not yet registered for next term. Advisors review every
flag before any outreach is sent.

Research consistently shows that timely, personalized advisor outreach at critical momentum
points significantly improves student persistence and credential completion, particularly for
students from underserved communities who may face additional barriers to re-enrollment. The
credit momentum approach is intentionally asset-based: it acknowledges what students have
already accomplished and meets them where they are, rather than framing non-registration as
a failure.

**Demo institution:** Redrock College is a fictional small rural community college with
limited administrative infrastructure and high advisor caseloads. All student records,
names, and program offerings are entirely fictional.

**A note on maturity:** This is a proof of concept built for demonstration purposes. It has
not been tested with real student data, and the synthetic dataset used here was designed to
exercise the agent's logic, not to represent any real institution or population. The code is
open-source and intended as a starting point for institutions or developers who want to adapt,
extend, or build upon it. Contributions and forks are welcome.

Developers: see the README for installation instructions and guidance on adapting Waypoint
for your institution.
    """)

# ── What Waypoint Does NOT Do ─────────────────────────────────────────────────
with st.expander("What Waypoint does NOT do"):
    st.markdown("""
Setting the right expectations before you explore the demo:

- **Does not update any SIS or CRM.** Advisor actions happen entirely outside Waypoint.
  No student records are modified.
- **Does not send emails.** Waypoint drafts outreach messages for advisor review.
  The advisor sends manually through their existing email or advising system.
- **Does not track outreach outcomes.** Once a message is drafted and copied,
  Waypoint has no visibility into whether it was sent, received, or acted upon.
- **Does not perform a degree audit.** Credit completion is used as a proxy.
  In a real deployment, a credits_remaining field from your SIS degree audit
  module would replace the hardcoded threshold calculations used here.
- **Does not store data between sessions.** The SQLite database is local and
  resets each time the pipeline runs. This is intentional for a demo context.
- **Requires an Anthropic API key.** Each pipeline run consumes a small number
  of tokens for ambiguous case reasoning and outreach drafting. You will need
  your own API key to run a local instance. See
  [Anthropic's pricing page](https://www.anthropic.com/pricing) for current costs.
    """)

# ── About the Demo Dataset ────────────────────────────────────────────────────
with st.expander("About the demo dataset"):
    st.markdown("""
Waypoint ingests a CSV export modeled on a realistic SIS export from Redrock College.
The dataset is entirely synthetic — all names, IDs, and records are fictional.

**Dataset summary:**
- **76 records** (75 unique students + 1 intentional duplicate to demonstrate deduplication)
- **3 program types:** Certificate (30 cr), Associate's (60 cr), Bachelor's (120 cr)
- **5 certificate programs:** Early Childhood Education, Administrative Office Technology,
  Redrock Language and Culture, Environmental Science Technology, Nursing Assistant
- **5 associate's programs:** Business Administration, Liberal Arts, Science, Education,
  Natural Resources
- **3 bachelor's programs:** Elementary Education, Business Administration, Redrock Studies

**Intentional data quality issues** (to demonstrate the ingestion layer):
- Mixed date formats in the advisor contact field
- Missing credits fields on 4 records
- Null registration status on 3 records
- Legacy program type codes on 2 records (e.g. CERT-ECE, AS-BUS)
- Mixed boolean formats (True/False and Y/N)
- One encoding artifact (accent character in a name field)
- One duplicate student record

**Flag distribution the dataset is designed to produce:**
- 8 deterministic Credit Momentum flags
- 6 deterministic One Course Away flags
- 9 ambiguous cases routed to Claude
- 10 records with data quality issues requiring human review
- Remaining records: clean, no intervention needed

**A note on variance:** The flag count you see after running the pipeline may vary
slightly from the numbers above. Deterministic flags are stable and will always produce
the same results. However, Claude's reasoning on ambiguous cases may produce different
decisions across runs. This is expected behavior. LLM outputs are not deterministic, and
a case Claude flags in one run may be dismissed in another depending on how it reasons
through the available evidence. This variance reflects the kind of judgment call a human
advisor would also weigh differently in different contexts.
    """)

    st.info("Running the demo pipeline typically takes 30 to 60 seconds. Claude evaluates each ambiguous case individually, which accounts for most of the processing time.")

    try:
        with open(CSV_PATH, "rb") as f:
            st.download_button(
                label="Download demo CSV",
                data=f,
                file_name="redrock_students_demo.csv",
                mime="text/csv",
            )
    except FileNotFoundError:
        st.warning("CSV file not found. Run: python data/generate_synthetic.py")

# ── Bottom Run Button (hidden after pipeline runs) ────────────────────────────
if not st.session_state.pipeline_run:
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 2])
    with col2:
        if st.button("▶ Run Demo", type="primary", use_container_width=True, key="run_bottom"):
            run_pipeline()
            st.rerun()
    render_footer()
    st.stop()

# ── Pipeline Summary ──────────────────────────────────────────────────────────
state = st.session_state.pipeline_state

if state.get("status") == "error":
    st.error(
        "The pipeline could not complete. Nothing was loaded or flagged.\n\n"
        + "\n\n".join(f"- {e}" for e in state.get("errors", []))
    )
    render_footer()
    st.stop()

summary = state.get("ingest_summary", {})

st.markdown("---")
col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Students Loaded", summary.get("records_loaded", 0))
col2.metric("Duplicates Removed", summary.get("duplicates_removed", 0))
col3.metric("Data Issues", summary.get("data_issues", 0))
col4.metric("Deterministic Flags", len(state.get("clear_flags", [])))
col5.metric("LLM Flags", len(state.get("llm_flags", [])))

llm_skipped = state.get("llm_skipped", 0)
if llm_skipped:
    st.warning(
        f"⚠️ {llm_skipped} ambiguous case(s) were not evaluated by Claude because "
        f"this run hit its token budget (MAX_TOKENS_PER_RUN in config.py). These "
        f"students were flagged by the rule engine as needing judgment, but did "
        f"not receive one — they will not appear below. Increase the budget or "
        f"re-run to review them."
    )

st.markdown("---")

# ── Load Flags ────────────────────────────────────────────────────────────────
flags = get_all_flags()

if not flags:
    st.warning("No flags generated. Check your CSV and run the pipeline again.")
    render_footer()
    st.stop()

# ── Filter Controls ───────────────────────────────────────────────────────────
col1, col2, col3 = st.columns(3)
with col1:
    filter_type = st.selectbox(
        "Flag type",
        ["All", "momentum_nudge", "one_course_away"],
        format_func=lambda x: {
            "All": "All flags",
            "momentum_nudge": "🟠 Credit Momentum",
            "one_course_away": "🟢 One Course Away"
        }.get(x, x)
    )
with col2:
    filter_source = st.selectbox(
        "Source",
        ["All", "deterministic", "llm", "llm_error"],
        format_func=lambda x: {
            "All": "All sources",
            "deterministic": "Deterministic rule",
            "llm": "Claude reasoning",
            "llm_error": "⚠️ Needs manual review"
        }.get(x, x)
    )
with col3:
    filter_decision = st.selectbox(
        "Decision status",
        ["All", "Pending", "Confirmed", "Dismissed"],
    )

# Apply filters
filtered_flags = flags
if filter_type != "All":
    filtered_flags = [f for f in filtered_flags if f["flag_type"] == filter_type]
if filter_source != "All":
    filtered_flags = [f for f in filtered_flags if f["flag_source"] == filter_source]
if filter_decision == "Pending":
    filtered_flags = [f for f in filtered_flags
                      if f["id"] not in st.session_state.decisions]
elif filter_decision == "Confirmed":
    filtered_flags = [f for f in filtered_flags
                      if st.session_state.decisions.get(f["id"]) == "confirmed"]
elif filter_decision == "Dismissed":
    filtered_flags = [f for f in filtered_flags
                      if st.session_state.decisions.get(f["id"]) == "dismissed"]

st.markdown(f"### Flags for Review ({len(filtered_flags)} shown)")

# ── Confidence Legend ─────────────────────────────────────────────────────────
with st.expander("What does confidence mean?"):
    st.markdown("""
**Confidence** reflects how certain Claude is about its recommendation, based on the
available data in the CSV export. It applies only to flags evaluated by Claude (ambiguous
cases). Deterministic rule-based flags are always high confidence.

- 🟢 **High** — The available data points clearly in one direction. Claude's recommendation
  is well-supported. Act on this flag with normal advisor judgment.
- 🟡 **Medium** — Claude recommends action but a meaningful data gap exists, such as
  unevaluated transfer credits or an unclear registration status. Verify the student's
  record before outreach.
- 🔴 **Low** — Claude flagged this student but the situation is genuinely ambiguous.
  Review the student's full record before acting. This flag may be dismissed after review.

Confidence is not a prediction of student success. It reflects the quality of the available
data and Claude's certainty about its own recommendation.
    """)

# ── Flag Cards ────────────────────────────────────────────────────────────────
for flag in filtered_flags:
    flag_id = flag["id"]
    decision = st.session_state.decisions.get(flag_id)
    if flag["flag_source"] == "llm_error":
        card_class = "flag-card-error"
    elif flag["flag_source"] == "llm":
        card_class = "flag-card-llm"
    else:
        card_class = "flag-card"

    with st.container():
        st.markdown(f'<div class="{card_class} flag-card">', unsafe_allow_html=True)

        col1, col2 = st.columns([4, 1])
        with col1:
            flag_emoji = "🟢" if flag["flag_type"] == "one_course_away" else "🟠"
            flag_label = "One Course Away" if flag["flag_type"] == "one_course_away" \
                else "Credit Momentum"
            if flag["flag_source"] == "llm_error":
                source_label = "⚠️ Needs Manual Review (Claude unavailable)"
            elif flag["flag_source"] == "llm":
                source_label = "Claude"
            else:
                source_label = "Rule"
            confidence = flag.get("confidence", "")
            confidence_emoji = {"high": "🟢", "medium": "🟡", "low": "🔴"}.get(confidence, "")
            confidence_str = f" · {confidence_emoji} {confidence} confidence" \
                if confidence else ""

            st.markdown(
                f"**{flag['first_name']} {flag['last_name']}** · "
                f"{flag_emoji} {flag_label} · "
                f"_{source_label}{confidence_str}_"
            )
            st.caption(
                f"{flag['program_type'].title()} in {flag['program_name']} · "
                f"{flag['credits_completed']:.0f} credits completed · "
                f"Transfer credits: {flag['transfer_credits'] or 0}"
            )

        with col2:
            if decision == "confirmed":
                st.success("✓ Confirmed")
            elif decision == "dismissed":
                st.warning("✗ Dismissed")

        if flag.get("reasoning"):
            st.markdown(f"**Reasoning:** {flag['reasoning']}")
        if flag.get("outreach_note"):
            st.info(f"💬 **Advisor note:** {flag['outreach_note']}")
        if flag.get("stop_out_history"):
            st.warning(f"Stop-out history: {flag['stop_out_history']}")
        if flag.get("registration_hold"):
            st.error("Registration hold on file")

        if not decision:
            col1, col2, col3 = st.columns([1, 1, 4])
            with col1:
                if st.button("✓ Confirm", key=f"confirm_{flag_id}", type="primary"):
                    st.session_state.decisions[flag_id] = "confirmed"
                    st.rerun()
            with col2:
                if st.button("✗ Dismiss", key=f"dismiss_{flag_id}"):
                    st.session_state.decisions[flag_id] = "dismissed"
                    st.rerun()

        if decision == "confirmed":
            msg_key = f"msg_{flag_id}"
            if msg_key not in st.session_state.outreach_messages:
                if st.button("✉️ Draft outreach email", key=f"draft_{flag_id}"):
                    with st.spinner("Drafting outreach email..."):
                        msg = generate_outreach_message(
                            flag,
                            flag["flag_type"],
                            flag.get("reasoning", "")
                        )
                        st.session_state.outreach_messages[msg_key] = msg
                    st.rerun()
            else:
                st.markdown("**Draft outreach email:**")
                st.text_area(
                    "Edit before sending",
                    value=st.session_state.outreach_messages[msg_key],
                    height=120,
                    key=f"edit_{flag_id}",
                    label_visibility="collapsed"
                )
                st.caption("Copy this message to your advising system or email client.")

        st.markdown('</div>', unsafe_allow_html=True)
        st.markdown("")

# ── Session Summary ───────────────────────────────────────────────────────────
if st.session_state.decisions:
    st.markdown("---")
    confirmed = sum(1 for d in st.session_state.decisions.values() if d == "confirmed")
    dismissed = sum(1 for d in st.session_state.decisions.values() if d == "dismissed")
    pending = len(flags) - len(st.session_state.decisions)
    col1, col2, col3 = st.columns(3)
    col1.metric("✓ Confirmed", confirmed)
    col2.metric("✗ Dismissed", dismissed)
    col3.metric("⏳ Pending", pending)

# ── Footer ────────────────────────────────────────────────────────────────────
render_footer()