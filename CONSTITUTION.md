# COINOSKOBI CONSTITUTION

Version: 1.0

Status: ACTIVE

Last Updated: 2026-08-07

---

# PREAMBLE

This Constitution defines the engineering principles, architectural rules, development process and governance of the Coinoskobi project.

Every contribution to the repository MUST comply with this document.

---

Coinoskobi Engineering Principle

Plan
→ Code
→ Compile
→ Import
→ Smoke Test
→ Commit
→ Push
→ Roadmap
→ Final Audit

No phase is complete until every step passes.

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

Coinoskobi is **NOT** designed to maximize trading frequency.

Its primary objective is **decision quality**.

---

# ARTICLE 2 — CORE VALUES

Every contribution must respect the following values.

- Simplicity
- Readability
- Maintainability
- Modularity
- Security
- Reliability
- Transparency

---

# ARTICLE 3 — ARCHITECTURE

The official pipeline is:

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

No module may bypass this pipeline.

---

# ARTICLE 4 — SINGLE RESPONSIBILITY

Every module must have one responsibility.

Examples

Scanner

only scans.

Analyzer

only analyzes.

Strategy

only decides.

Paper

only manages simulated trades.

Portfolio

only reports portfolio information.

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

print() statements used only for debugging shall be removed before merge.

---

# ARTICLE 7 — DEVELOPMENT PROCESS

Every feature follows:

Planning

↓

Implementation

↓

Compile

↓

Manual Test

↓

Review

↓

Commit

↓

Push

No feature skips this process.

---

# ARTICLE 8 — COMMITS

Every commit must have exactly one purpose.

Recommended prefixes

feat:

fix:

refactor:

docs:

test:

style:

Example

feat(scanner): improve candidate filtering

---

# ARTICLE 9 — SECURITY

Private keys shall never be committed.

.env shall never be committed.

Secrets must remain outside the repository.

---

# ARTICLE 10 — PAPER FIRST

Paper Trading is mandatory.

Live Trading cannot begin until Paper Trading proves stability.

---

# ARTICLE 11 — LIVE TRADING

Live Trading is disabled by default.

Enabling Live Trading requires explicit approval.

---

# ARTICLE 12 — ROADMAP GOVERNANCE

The official roadmap consists of:

Phase 0

↓

Phase 15

Phase 15 is final.

Phase 16 SHALL NEVER be created.

Future work shall continue using:

Release

Milestone

Sprint

Patch

Hotfix

---

# ARTICLE 13 — PROJECT DOCUMENTATION

The repository maintains:

README.md

CONSTITUTION.md

ROADMAP.md

PROJECT_STATUS.md

CHANGELOG.md

ARCHITECTURE.md

CONTRIBUTING.md

roadmap.json

These documents are part of the project.

---

# ARTICLE 14 — PERFORMANCE

Correctness has priority over optimization.

Premature optimization is discouraged.

Performance improvements must be measurable.

---

# ARTICLE 15 — CODE QUALITY

Every commit must:

Compile successfully.

Import successfully.

Keep the pipeline operational.

Avoid unnecessary complexity.

---

# ARTICLE 16 — OBSERVATION PRINCIPLE

Observation never stops.

Even when a trade is rejected,

the system continues to:

observe,

collect evidence,

score,

learn.

Risk blocks execution,

not observation.

---

# ARTICLE 17 — ETHICS

Coinoskobi shall never be developed for:

unauthorized access,

malicious activity,

market manipulation,

fraud,

or illegal purposes.

The platform exists to help users make safer decisions.

---

# ARTICLE 18 — GOVERNANCE

This Constitution is version controlled.

Every modification requires:

- version increment
- changelog entry
- commit

---

# ARTICLE 19 — DEFINITION OF DONE

A task is complete only if:

- Code is implemented.
- Compile succeeds.
- Manual testing succeeds.
- Documentation is updated.
- Roadmap is updated.
- Project Status is updated.
- Changelog is updated.
- Commit is pushed.

---

# ARTICLE 20 — FINAL RULE

If a future change conflicts with this Constitution,

the Constitution takes precedence.

This document defines the engineering identity of Coinoskobi.

# Development Lifecycle (Mandatory)

Every implementation phase in Coinoskobi MUST follow the same engineering lifecycle.

No phase is considered complete unless every step below has been completed successfully.

## Required Workflow

1. Plan
   - Define the objective.
   - Define acceptance criteria.
   - Confirm architecture impact.

2. Code
   - Implement only the planned scope.
   - Avoid unrelated refactoring.

3. Compile
   - All Python modules must compile successfully.

4. Import Validation
   - All affected modules must import without errors.

5. Smoke Test
   - Verify the implemented feature with a minimal functional test.

6. Commit
   - Create a single-purpose commit with a clear message.

7. Push
   - Push only after successful compile and smoke test.

8. Roadmap Update
   - Mark the completed phase in ROADMAP.md.
   - Update PROJECT_STATUS.md if applicable.

9. Final Audit
   - Verify:
     - compile
     - import
     - smoke test
     - git clean
     - roadmap updated
     - documentation updated

Only after all nine steps are complete may a phase be considered CLOSED.

No step may be skipped.

## One Phase - One Purpose Rule

Each phase must have a single clear objective.

A phase must not introduce unrelated features.

If a task belongs to another phase, it must be postponed.

Small, reviewable commits are preferred over large mixed changes.
