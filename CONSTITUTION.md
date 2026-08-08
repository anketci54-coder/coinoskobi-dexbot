# COINOSKOBI CONSTITUTION

Version: 1.1

Status: ACTIVE

Last Updated: 2026-08-08

---

# PREAMBLE

This Constitution defines the engineering principles, architecture, governance and development standards of the Coinoskobi project.

Every contribution to this repository MUST comply with this Constitution.

---

# COINOSKOBI DEVELOPMENT RULE

Every phase follows the same workflow.

Plan
↓

Code
↓

Verify
↓

Commit
↓

Push
↓

Close

Verify includes:

- Compile
- Import Validation
- Tests
- Smoke Tests (when applicable)

A phase is NOT complete until the Close step has successfully finished.

---

# ARTICLE 1 — MISSION

Coinoskobi is a modular Decision Support Platform for decentralized exchanges.

Its mission is to:

- Discover opportunities
- Analyze market quality
- Evaluate trading risks
- Simulate trading through Paper Trading
- Learn from historical outcomes
- Assist human decision making

Coinoskobi is NOT designed to maximize trading frequency.

Its primary objective is decision quality.

---

# ARTICLE 2 — CORE VALUES

Every contribution must respect these principles.

- Simplicity
- Readability
- Maintainability
- Modularity
- Reliability
- Security
- Transparency

---

# ARTICLE 3 — ARCHITECTURE

The official processing pipeline is:

Scanner

↓

Cache

↓

Filter

↓

Analyzer

↓

Risk Engine

↓

Strategy Engine

↓

Paper Trading

↓

Portfolio

↓

API

No module may bypass this architecture.

---

# ARTICLE 4 — SINGLE RESPONSIBILITY

Every module must have exactly one responsibility.

Examples:

Scanner
- scans

Analyzer
- analyzes

Strategy
- decides

Paper
- manages simulated trades

Portfolio
- reports portfolio information

---

# ARTICLE 5 — CLEAN REPOSITORY

The repository shall never contain:

- dead code
- obsolete modules
- experimental files
- temporary scripts
- duplicated implementations
- abandoned prototypes

Unused code must be removed.

---

# ARTICLE 6 — PATCH POLICY

Temporary fixes are prohibited.

Debug code must never be committed.

Debug-only print() statements must be removed before commit.

---

# ARTICLE 7 — DEVELOPMENT PROCESS

Every implementation must follow the Coinoskobi Development Rule.

No phase may skip:

- Plan
- Code
- Verify
- Commit
- Push
- Close

---

# ARTICLE 8 — COMMITS

Each commit must have exactly one purpose.

Recommended prefixes:

- feat:
- fix:
- refactor:
- docs:
- test:
- style:

Example:

feat(scanner): improve candidate filtering

---

# ARTICLE 9 — SECURITY

Private keys must never be committed.

.env files must never be committed.

Secrets must remain outside the repository.

---

# ARTICLE 10 — PAPER FIRST

Paper Trading is mandatory.

Live Trading cannot begin until Paper Trading demonstrates stable operation.

---

# ARTICLE 11 — LIVE TRADING

Live Trading is disabled by default.

Enabling Live Trading requires explicit approval.

---

# ARTICLE 12 — ROADMAP GOVERNANCE

The official roadmap ends at:

Phase 15

Phase 16 SHALL NEVER exist.

Future work continues using:

- Release
- Milestone
- Sprint
- Patch
- Hotfix

---

# ARTICLE 13 — PROJECT DOCUMENTATION

The following documents are mandatory:

- README.md
- CONSTITUTION.md
- ROADMAP.md
- PROJECT_STATUS.md
- CHANGELOG.md
- ARCHITECTURE.md
- CONTRIBUTING.md
- roadmap.json

They are part of the project and must remain synchronized.

---

# ARTICLE 14 — PERFORMANCE

Correctness has priority over optimization.

Premature optimization is discouraged.

Performance improvements must be measurable.

---

# ARTICLE 15 — CODE QUALITY

Every change must:

- Compile successfully.
- Import successfully.
- Keep the pipeline operational.
- Avoid unnecessary complexity.
- Preserve readability.

---

# ARTICLE 16 — OBSERVATION PRINCIPLE

Observation never stops.

Even when execution is rejected, the system continues to:

- Observe
- Collect evidence
- Score
- Learn

Risk blocks execution.

Risk never blocks observation.

---

# ARTICLE 17 — ETHICS

Coinoskobi shall never be developed for:

- unauthorized access
- malicious activity
- market manipulation
- fraud
- illegal purposes

The platform exists to help users make safer decisions.

---

# ARTICLE 18 — GOVERNANCE

This Constitution is version controlled.

Every modification requires:

- Version increment
- Changelog entry
- Commit

---

# ARTICLE 19 — DEFINITION OF DONE

A task is complete only after the Close step.

Close requires:

- Verify passed
- Documentation updated (when required)
- Roadmap updated (when required)
- Project Status updated (when required)
- Changelog updated (when required)
- Commit pushed

---

# ARTICLE 20 — ONE PHASE, ONE PURPOSE

Each phase must have one clear objective.

A phase must not introduce unrelated features.

Tasks belonging to another phase shall be postponed.

Prefer small, reviewable commits over large mixed commits.

---

# ARTICLE 21 — FINAL RULE

If any future change conflicts with this Constitution,

this Constitution takes precedence.

It defines the engineering identity of Coinoskobi.
