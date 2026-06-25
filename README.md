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
- Outreach drafting uses Claude Haiku (fast, low cost) only when an advisor
  confirms a flag and requests a draft
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
acknowledges what students have already accomplished rather than framing non-registration
as a failure.

Key references:
- EAB Navigate360 research on proactive advising and stop-out prevention
- Georgia State University's Pounce chatbot and early alert outcomes
- Civitas Learning research on credit momentum as a leading persistence indicator

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