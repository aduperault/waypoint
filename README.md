# 🧭 Waypoint — Student Success Nudge Agent
**[▶ Live Demo](https://waypoint.streamlit.app/)** · **[GitHub](https://github.com/aduperault/waypoint)**
**A proof-of-concept AI agent for higher education student success, built for institutions with limited resources, siloed systems, and connectivity constraints.**

Waypoint demonstrates how a small institution can begin leveraging AI at the "crawl" stage of a crawl → walk → run adoption framework — no CRM integration, no cloud platform, no complex infrastructure required.

---

## What Waypoint Does

Waypoint ingests a single CSV export from any Student Information System (SIS) and surfaces two types of advisor nudges:

- 🟠 **Credit Momentum Nudge** — An active student is making progress but has not yet registered for next term
- 🟢 **One Course Away** — A student is within 3 credits of a credential milestone and has not registered

Advisors review every flag before any outreach is sent. Waypoint drafts the outreach email — the advisor sends it.

### Two-Tier Architecture

| Tier | What it does | When it runs |
|---|---|---|
| **Deterministic rules** | Evaluates clear cases instantly using credit thresholds and registration status | All students |
| **Claude LLM reasoning** | Evaluates ambiguous cases — stop-out patterns, transfer credits, unknown hold status | Ambiguous cases only |

The batch architecture is intentional: it minimizes token usage, processing overhead, and API dependency, making Waypoint viable even in low-connectivity environments.

---

## What Waypoint Does NOT Do

- **Does not update any SIS or CRM.** No student records are modified.
- **Does not send emails.** Waypoint drafts outreach messages. The advisor sends manually.
- **Does not track outreach outcomes.** No visibility into whether messages were sent or received.
- **Does not perform a degree audit.** Credit completion is used as a proxy. See Design Assumptions below.
- **Does not store data between sessions.** The SQLite database resets each pipeline run.
- **Requires an Anthropic API key.** You will need your own key to run a local instance.

---

## Demo Institution

**Redrock College** is a fictional small rural community college with limited administrative infrastructure and high advisor caseloads. The institution's cultural context reflects the bilingual, Indigenous-rooted community it serves, as represented in the student names and program offerings. All student records are entirely fictional.

---

## Quick Start

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)
- Git

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/aduperault/waypoint.git
cd waypoint

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate
# On Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install anthropic langgraph pandas streamlit python-dotenv

# 4. Add your Anthropic API key
cp .env.example .env
# Open .env and replace the placeholder with your actual key:
# ANTHROPIC_API_KEY=sk-ant-your-key-here

# 5. Generate the synthetic dataset
python data/generate_synthetic.py

# 6. Run the app
streamlit run app.py
```

The app will open automatically in your browser at `http://localhost:8501`.

Click **▶ Run Demo** to ingest the student CSV and generate flags. The pipeline takes approximately 30 to 60 seconds — Claude evaluates each ambiguous case individually, which accounts for most of the processing time.

---

## Project Structure
waypoint/

├── app.py                          # Streamlit advisor UI

├── config.py                       # Central configuration and thresholds

├── .env                            # Your Anthropic API key (never committed)

├── .env.example                    # API key template

├── waypoint/

│   ├── agent.py                    # LangGraph orchestration

│   ├── ingest.py                   # CSV normalization and ingestion

│   ├── rules.py                    # Deterministic flag engine

│   ├── llm.py                      # Claude reasoning and outreach drafting

│   └── db.py                       # SQLite schema and operations

├── data/

│   ├── generate_synthetic.py       # Reproducible synthetic dataset generator

│   └── synthetic/

│       └── redrock_students.csv    # Generated demo dataset

└── tests/

├── test_ingest.py

└── test_rules.py
---

## Adapting Waypoint for Your Institution

### 1. Map your SIS column names

Waypoint's ingestion layer recognizes common column name variants automatically.
Open `waypoint/ingest.py` and find the `FIELD_ALIASES` dictionary. Add your SIS
export column names to the relevant alias lists if they are not already there:

```python
FIELD_ALIASES = {
    "credits_completed": ["credits_completed", "credits_earned", "earned_credits", ...],
    "next_term_registered": ["next_term_registered", "registered_next", ...],
    ...
}
```

### 2. Update the registration deadline

In `config.py`:

```python
REGISTRATION_DEADLINE = "2025-08-01"  # Update to your actual deadline
```

### 3. Update credential thresholds

In `config.py`:

```python
CREDENTIAL_THRESHOLDS = {
    "certificate": 30,
    "associates": 60,
    "bachelors": 120,
}
```

Adjust these to match your institution's program credit requirements.

### 4. Ideally — export credits_remaining from your SIS

The most important adaptation for real deployment: if your SIS can export a
`credits_remaining` field from its degree audit module, add it to the CSV and
update `waypoint/rules.py` to use it directly instead of calculating from
thresholds. This eliminates the hardcoded threshold limitation entirely and
gives you accurate, degree-audit-verified remaining credit counts.

---

## Design Assumptions

These are intentional POC simplifications that a real deployment would address:

| Assumption | POC approach | Real deployment |
|---|---|---|
| Credits remaining | Calculated from hardcoded thresholds | Exported directly from SIS degree audit |
| Program requirements | Single credit threshold per credential type | Full degree audit integration |
| Data storage | Local SQLite, resets each run | Persistent database with run history |
| Email sending | Draft only, advisor copies manually | Integration with advising platform or email system |
| Outreach tracking | None | CRM or advising platform integration |
| Authentication | None | Institution SSO |

---

## Architecture

Waypoint uses a four-node LangGraph agent graph:
ingest → rule_engine → llm_evaluation → save_flags
- **ingest** — Reads and normalizes the CSV into SQLite
- **rule_engine** — Applies deterministic rules, produces clear flags and ambiguous cases
- **llm_evaluation** — Sends ambiguous cases to Claude Sonnet for reasoning
- **save_flags** — Persists all flags to the database for advisor review

LLM errors are non-fatal: if Claude is unavailable, deterministic flags still save
and the pipeline completes with a partial result.

### Token Usage

Waypoint is designed to minimize API costs:

- Deterministic rules handle the majority of cases with zero token usage
- Only genuinely ambiguous cases go to Claude (typically 5-15 per batch run)
- Outreach drafting uses Claude Haiku (fast, low cost) only when an advisor confirms a flag and requests a draft
- A token budget cap in `config.py` prevents runaway costs

---

## A Note on Flag Count Variance

The rule engine produces consistent deterministic flags on every run. However,
Claude's reasoning on ambiguous cases may vary slightly between runs — this is
expected LLM behavior. A case flagged in one run may be dismissed in another
depending on how Claude reasons through the available evidence. This variance
reflects the kind of judgment call a human advisor would also weigh differently
in different contexts. The advisor confirmation step is the appropriate safety
valve for this uncertainty.

---

## Crawl → Walk → Run

Waypoint is explicitly designed as the **crawl** stage:

| Stage | What it looks like |
|---|---|
| **Crawl (Waypoint)** | CSV ingestion, local SQLite, batch LLM, advisor confirms all flags |
| **Walk** | SIS API integration, persistent database, degree audit connection, basic outreach tracking |
| **Run** | Real-time triggers, multi-signal risk models, CRM integration, outcome measurement, equity dashboards |

---

## Research Context

Research consistently shows that timely, personalized advisor outreach at critical
momentum points significantly improves student persistence and credential completion,
particularly for students from underserved communities who may face additional barriers
to re-enrollment. The credit momentum approach is intentionally asset-based: it
acknowledges what students have already accomplished rather than framing
non-registration as a failure.

Key references:
- EAB Navigate360 research on proactive advising and stop-out prevention
- Georgia State University's Pounce chatbot and early alert outcomes
- Civitas Learning research on credit momentum as a leading persistence indicator

---

## Customizing and Extending Waypoint

Waypoint is designed in layers, which makes it straightforward to adapt without
touching the core agent logic.

### Changing the UI or Branding

All of the visual interface lives in a single file: `app.py`. The underlying
agent — the rules engine, Claude reasoning, data ingestion, and database — lives
in the `waypoint/` folder and does not need to change if you want a different look
or interface.

**If you want to restyle for your institution:**
- Colors, fonts, and card styles are in the CSS block at the top of `app.py`
- Add your institution logo with `st.image()` in the header section
- Replace references to "Redrock College" in `app.py` and `config.py`
- Adjust the description text to reflect your institution's context

**If you want a completely different interface:**
A developer can replace `app.py` entirely with a different frontend framework
(Flask, Django, React, or any other web stack) while keeping all the agent logic
unchanged. The entry point is always the same one line:

```python
from waypoint.agent import run_waypoint
state = run_waypoint("path/to/your/students.csv")
```

Everything else — ingestion, rules, Claude reasoning, flag storage — runs
automatically and returns a state object the new interface can use however it needs.

### Choosing a Different Host

Waypoint runs anywhere Python runs. Streamlit Community Cloud is used here for
convenience, but a developer or system administrator could deploy it to:

- **Their institution's own servers** — any Linux server with Python 3.11+ works
- **Heroku or Railway** — simple cloud hosting with minimal configuration
- **Azure, AWS, or Google Cloud** — for institutions already using one of these platforms
- **A local network only** — for institutions that want to keep student data entirely
  on-premises and off the public internet (recommended for production use)

The only external dependency is the Anthropic API call for ambiguous case reasoning.
Everything else — the database, the rules engine, the UI — runs fully locally.

---

## Contributing

Waypoint is open-source and intended as a starting point. Contributions welcome:

- Additional SIS column name aliases
- Support for additional credential types
- Improved ambiguity detection rules
- Test coverage for `test_ingest.py` and `test_rules.py`
- Deployment guides for specific SIS platforms

Fork the repo, make your changes, and open a pull request.

---

## Built By

[AnneAble Consulting](https://www.anneable.com/) — AI enablement strategy and
implementation for education, nonprofit, and public sector organizations.

Questions or feedback: [anneable.com](https://www.anneable.com/)

---

## License

MIT License — free to use, adapt, and distribute with attribution.

---

*Waypoint is a proof of concept. It has not been tested with real student data
and is not intended for production use without further development and validation.*