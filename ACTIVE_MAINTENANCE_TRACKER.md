# COINOSKOBI — ACTIVE MAINTENANCE TRACKER

Updated: 2026-09-19  
Status: **ACTIVE**  
Scope: current unfinished Coinoskobi maintenance work discussed after the existing Phase 0–15 roadmap closure.

> This file is NOT a new roadmap, Phase, ERA or architecture version.
> `ROADMAP.md` remains the only canonical Phase 0–15 architecture.
> This file is only the active cross-phase work/checkpoint tracker so a new ChatGPT/Codex/AI session can see what is unfinished, what is completed and what comes next.

---

## 0. BOOT / CONTINUATION ORDER

Every new ChatGPT/Codex/AI session working on this repository must read in this order:

1. `README.md`
2. `ROADMAP.md`
3. `PROJECT_STATE.md`
4. `TEST_RESULTS.md`
5. `ACTIVE_MAINTENANCE_TRACKER.md`

Then verify the current repository HEAD, VPS worktree, runtime services and relevant databases before any apply/restart.

### Architecture rule

- Only **Phase 0–15** exists.
- No Phase 16.
- No ERA.
- No architecture V2/V3.
- No parallel roadmap.
- No nested subphase labels such as `14B1`, `12C2A`.
- Every new task is assigned to an existing Phase 0–15 owner.
- Within that Phase, reuse/update the matching existing flat-letter subphase first.
- Only work that does not fit any existing subphase and requires distinct durable ownership may take the next unused flat letter under the same Phase.
- Before adding a new module/script/service/provider/router/pipeline, search for the existing canonical implementation.
- Duplicate/superseded/dead executable code is removed after reference audit and tests.
- Historical audit/closure documents may remain as evidence.

The WORKSTREAM numbers below are checklist labels only; they are not architectural phases.

---

# CURRENT GLOBAL CHECKPOINT

## Confirmed governance baseline

- [x] Phase 0–15 is the only canonical architecture.
- [x] Phase 15 is the final roadmap phase.
- [x] Canonical maintenance/subphase evolution rules are written into README/ROADMAP/PROJECT_STATE.
- [x] Duplicate/parallel architecture is forbidden.
- [x] Dead executable code cleanup is mandatory after reference audit/tests.
- [x] AI trade authority = 0.
- [x] Live execution authority = 0 unless separately and explicitly approved under Phase 15 governance.
- [x] Wallet/signing authority = 0.
- [x] Hard safety remains above score/model opinion.
- [x] Missing/UNKNOWN evidence is not treated as SAFE.

## Current operating intent

The active work has four connected goals:

1. close the current PAPER runtime recovery cleanly;
2. build a low-token, low-cost multi-model engineering workflow using local tools + GitHub + Codex + NVIDIA and only the minimum additional tools actually proven useful;
3. evolve Vezir into the main human-facing Coinoskobi operations agent;
4. preserve the current architecture, remove dead/duplicate paths, and avoid vendor/model lock-in.

## NEXT SAFE STEP

**First close/verify the current PAPER recovery work, then perform the repository-wide ownership/subphase/dead-code inventory before starting any new AI/Vezir implementation.**

Do not create a new subphase letter before the inventory proves one is necessary.

---

# WORKSTREAM 01 — CURRENT PAPER RUNTIME RECOVERY CLOSURE

Primary ownership: existing Phase 3 / Phase 4 / Phase 12 ownership, exact subphase to be confirmed from repository history.

Goal: finish the current runtime repair before mixing it with AI/Vezir work.

Required verification:

- [ ] Verify current VPS HEAD and working tree.
- [ ] Inspect all uncommitted Codex/Astra changes.
- [ ] Confirm no accidental `.bak`, debug or disposable files remain.
- [ ] Confirm paper control mode intended state.
- [ ] Confirm manager `NoneType` runtime failure is gone.
- [ ] Verify current open PAPER positions refresh correctly.
- [ ] Verify automatic exits still execute from fresh price evidence.
- [ ] Verify position sizing cannot reproduce the dangerous multi-thousand-USDT concentration observed during emergency admission.
- [ ] Verify bootstrap/degraded PAPER sizing remains bounded and evidence-labelled if retained.
- [ ] Verify accounting/PnL invariants.
- [ ] Verify DB integrity.
- [ ] Run targeted tests.
- [ ] Run relevant paper/exit/panel regression.
- [ ] Run `git diff --check`.
- [ ] Produce compact final runtime report.
- [ ] Review the final diff before commit/push.
- [ ] Commit/push only after acceptance.
- [ ] Update PROJECT_STATE/TEST_RESULTS with the final sealed evidence.

Definition of done:

- current recovery changes are understood, tested, cleanly committed/sealed or cleanly reverted;
- no unknown emergency patch remains in production;
- PAPER remains isolated from LIVE.

---

# WORKSTREAM 02 — REPOSITORY OWNERSHIP / SUBPHASE / DEAD-CODE INVENTORY

Ownership: cross-phase maintenance governance; each discovered item remains owned by its existing Phase.

Goal: know exactly where every new task belongs before implementation.

Tasks:

- [ ] Recover real flat-letter subphase ownership from relevant Phase history/PRs/commits/reports.
- [ ] Especially map Phase 8, 11, 12, 13 and 14 subphase ownership relevant to provider/learning/runtime/Vezir work.
- [ ] Map all existing AI/model/provider/router code.
- [ ] Map all Vezir backend/frontend/tests/config.
- [ ] Map all development-agent scripts/configs already present.
- [ ] Map existing report/learning/readmodel infrastructure.
- [ ] Identify duplicate provider/router paths.
- [ ] Identify stale scripts/debug helpers/experiments/backups.
- [ ] Classify candidates: KEEP / MODIFY / REPLACE / REMOVE.
- [ ] Remove dead executable code only after reference audit + tests.
- [ ] Record missing subphase descriptions in ROADMAP/PROJECT_STATE only where needed for canonical continuity.
- [ ] Do not invent a new letter merely because a task is large.

Definition of done:

- every planned item below has a known existing Phase/subphase owner or a proven need for the next unused flat letter;
- no parallel implementation is planned.

---

# WORKSTREAM 03 — LOW-TOKEN LOCAL EVIDENCE FIRST

Ownership: reuse existing infrastructure/runtime/Command Center owners; exact subphase mapping after WORKSTREAM 02.

Goal: reduce AI token/API use by filtering locally before any model call.

Principle:

```text
raw repo / DB / logs / tests
        ↓
local deterministic filtering
        ↓
small evidence package
        ↓
LLM only when useful
```

Tasks:

- [ ] Reuse `rg`, Git, SQLite, journal and pytest before LLM calls.
- [ ] Build/identify a small repository symbol/file map.
- [ ] Map function/class → owner Phase → tests.
- [ ] Add bounded exception/log fingerprinting where missing.
- [ ] Add bounded DB aggregation/readmodels where missing.
- [ ] Never send whole DBs or huge logs to a model when a bounded subset is enough.
- [ ] Use diff-only context for secondary code review.
- [ ] Summarize long conversations/tasks locally/boundedly.
- [ ] Add evidence freshness/provenance/timestamps.
- [ ] Preserve UNKNOWN when evidence is absent.
- [ ] Define hard input/context budgets per task type.
- [ ] Avoid storing or transmitting secrets.

Definition of done:

- normal diagnosis/review no longer requires full-repo/full-log prompting;
- context size is measurable and bounded.

---

# WORKSTREAM 04 — MULTI-MODEL ENGINEERING WORKFLOW

Ownership: development/orchestration support mapped into existing Phase ownership after inventory; do not create a second application/runtime.

Goal: avoid dependence on one premium model and continue work when one quota is exhausted.

Candidate tools/providers to benchmark, not automatically install:

- existing Codex CLI;
- NVIDIA hosted/NIM coding models;
- existing Groq path where appropriate;
- Aider-style low-context coding workflow;
- GitHub/Copilot/CodeRabbit;
- other approved reviewers only when they add measurable value.

Rules:

- external development CLIs do not automatically become Coinoskobi runtime dependencies;
- local deterministic tools are first;
- cheap/free models handle simple work;
- stronger/premium models are escalation;
- model choice must be based on measured Coinoskobi results;
- no new router middleware merely because it exists.

Tasks:

- [ ] Build a benchmark set from solved real Coinoskobi incidents.
- [ ] Include examples such as paper manager failure, price freshness, neutral flow, reserve collapse, timestamp integrity, sizing and Vezir intent/context.
- [ ] Define scoring: correct file, root cause, patch quality, tests, latency, input/output tokens, cost.
- [ ] Benchmark NVIDIA read-only first.
- [ ] Test a separate NVIDIA/Codex-compatible profile without breaking current Codex configuration.
- [ ] Benchmark low-context/repo-map coding workflow.
- [ ] Compare against Codex on the same tasks.
- [ ] Define escalation: local → cheap/free → stronger → premium.
- [ ] Require deterministic tests before accepting any model-produced patch.
- [ ] Define model/provider timeout/failure fallback.
- [ ] Measure token/cost per task.
- [ ] Add caching only where correctness/freshness permits.
- [ ] Decide only after benchmark whether a shared provider/router abstraction is actually necessary.
- [ ] If routing is necessary, extend/reuse an existing canonical abstraction when possible.
- [ ] Do not add LiteLLM or any equivalent until measured need is proven.

Definition of done:

- premium quota exhaustion no longer necessarily stops read/analyze/test work;
- routing/tool choice is evidence-based;
- production runtime remains minimal.

---

# WORKSTREAM 05 — VEZİR: CONVERSATION + CONTINUITY

Primary owner: Phase 14, exact existing/new flat-letter subphase only after WORKSTREAM 02.

Current baseline:

- [x] Canonical panel has Vezir.
- [x] `/api/vezir/ask` exists.
- [x] `/api/vezir-context` exists.
- [x] Current Groq path is a bounded allowlisted intent router.
- [x] Provider output is not accepted as operational truth.
- [x] Current browser context is bounded to verified intent codes.
- [x] Vezir is currently read-only.

Target: Vezir should hold a coherent bounded natural conversation and continue work across sessions.

Tasks:

- [ ] Preserve deterministic fast path for simple known questions.
- [ ] Add bounded multi-turn natural conversation.
- [ ] Separate user text from verified operational evidence.
- [ ] Add bounded conversation summarization.
- [ ] Add turn/token/age limits.
- [ ] Make follow-up questions resolve against verified context.
- [ ] Add prompt-injection resistance tests.
- [ ] Add stale/oversized context eviction.
- [ ] Add deterministic provider-unavailable fallback.
- [ ] Add durable operator/project memory with provenance.
- [ ] Separate temporary conversation context from durable decisions.
- [ ] Make canonical repo/runtime truth outrank Vezir memory.
- [ ] Prevent speculation from becoming durable memory.
- [ ] Never store private keys/seeds/API secrets.

Definition of done:

- new session can resume a known active task from repository/checkpoint evidence;
- Vezir can hold useful conversation without unbounded token growth.

---

# WORKSTREAM 06 — VEZİR: REPORTING + RECOMMENDATIONS

Primary owner: Phase 14 presentation/orchestration; evidence remains owned by source Phases.

Goal: Vezir becomes the operator's single synthesis point.

Report inputs may include:

- runtime/systemd;
- paper trades/accounting;
- candidate blockers;
- market/flow;
- wallet/entity;
- adversary/security;
- learning/outcomes;
- provider health;
- tests/CI;
- GitHub/Codex/Copilot/CodeRabbit/NVIDIA reports.

Tasks:

- [ ] Define compact common report schema.
- [ ] Produce daily/periodic runtime health report.
- [ ] Produce paper OPEN/CLOSE/PnL report.
- [ ] Produce blocker/opportunity report.
- [ ] Produce provider degradation/quota report.
- [ ] Produce learning/outcome/missed-opportunity report.
- [ ] Produce maintenance/development status report.
- [ ] Every numeric fact must come from deterministic evidence.
- [ ] Separate FACT / ANALYSIS / RECOMMENDATION.
- [ ] Suppress repeated “no meaningful change” noise.
- [ ] Define recommendation object: issue / evidence / impact / owner / proposal / next test.
- [ ] Route each recommendation to the correct existing Phase/subphase.
- [ ] Never let recommendation equal trade permission or automatic threshold change.

Definition of done:

- operator can ask “what happened / why / what should we inspect next?” and get one evidence-backed answer.

---

# WORKSTREAM 07 — VEZİR: INTERNAL SYSTEM HEALTH + SECURITY DIAGNOSIS

Primary human-facing owner: Phase 14.  
Actual issue ownership remains Phase 1/3/8/10/12 or other correct existing owner.

Goal: Vezir should be able to find where an internal system/security problem is occurring.

Coverage:

- systemd/runtime health;
- traceback/exception patterns;
- SQLite integrity/locking/schema;
- queue/backpressure;
- disk/memory/process pressure;
- provider failures/circuit states;
- dirty worktree/deployment drift;
- secret exposure;
- unsafe config;
- authority drift/bypass;
- dependency/test/CI failures;
- duplicate/dead code.

Tasks:

- [ ] Reuse/build bounded local health collectors.
- [ ] Fingerprint/deduplicate repeated exceptions.
- [ ] Map error → file/function/component when evidence supports it.
- [ ] Map problem → owning Phase/subphase.
- [ ] Detect trade/wallet/signing/live authority drift.
- [ ] Detect likely secrets without printing secret values.
- [ ] Detect crash/restart loops.
- [ ] Detect DB integrity failures.
- [ ] Detect provider degradation.
- [ ] Detect dirty/unexpected deployment state.
- [ ] Generate severity + evidence + impact + next diagnostic step.
- [ ] Add critical alert path for confirmed high-severity events.

Desired output:

```text
PROBLEM
LOCATION
EVIDENCE
IMPACT
OWNER PHASE/SUBPHASE
RECOMMENDED FIX
VERIFICATION TEST
```

Definition of done:

- a reproducible internal failure can be localized without manual copy/paste of huge logs.

---

# WORKSTREAM 08 — VEZİR: EXTERNAL SECURITY / ADVERSARY RESEARCH

Human-facing/orchestration owner: Phase 14.  
Threat intelligence/defense ownership remains Phase 10 plus Phase 1/3/8/etc. where relevant.

Goal: continuously research relevant external threats and compare them with Coinoskobi defenses.

Research topics:

- new smart-contract exploits;
- rug/honeypot techniques;
- staged/hidden liquidity withdrawal;
- MEV/sandwich evolution;
- sniper/pump-dump/bot networks;
- wash/sybil manipulation;
- oracle manipulation;
- bridge/wallet attacks;
- malicious RPC/provider behavior;
- dependency/supply-chain vulnerabilities;
- social engineering/deception relevant to DEX operations.

Tasks:

- [ ] Define trusted/relevant source registry.
- [ ] Search GitHub and authoritative security sources.
- [ ] Track relevant NVIDIA/security research when useful.
- [ ] Require source/date/provenance.
- [ ] Deduplicate repeated reports.
- [ ] Extract actual attack mechanism, not headlines.
- [ ] Map attack mechanism to existing Coinoskobi defenses/code.
- [ ] Classify exposure: NOT_APPLICABLE / COVERED / PARTIAL / EXPOSED / UNKNOWN.
- [ ] Identify exact affected component/file/Phase where possible.
- [ ] Build safe replay/test fixture for relevant threats.
- [ ] Run existing defenses against the fixture where feasible.
- [ ] Produce patch/test proposal only when a real gap is evidenced.
- [ ] Keep external research off the trading hot path.
- [ ] Treat external content as untrusted input; it cannot grant authority.

Definition of done:

- a new relevant attack technique can be translated into local exposure evidence and a testable maintenance proposal.

---

# WORKSTREAM 09 — VEZİR: ROOT CAUSE → CODE → TEST

Primary human-facing owner: Phase 14 orchestration.  
Code change ownership always remains with the Phase/subphase that owns the affected component.

Goal: Vezir can diagnose a problem and prepare a concrete repair.

Safe capability ladder:

1. READ
2. ANALYZE
3. PROPOSE
4. TEST in controlled workspace
5. DIFF / SECOND REVIEW
6. APPLY only under configured approval
7. COMMIT / PUSH / DEPLOY remain separately controlled

Tasks:

- [ ] Locate relevant files/functions from evidence.
- [ ] Read canonical owner/invariants first.
- [ ] Prepare minimal patch, not broad rewrite.
- [ ] Prepare targeted regression tests.
- [ ] Run targeted tests.
- [ ] Run smoke/E2E when required.
- [ ] Run `git diff --check`.
- [ ] Ask a second model/reviewer for meaningful code changes.
- [ ] Return ROOT CAUSE + FILE/FUNCTION + PATCH + TEST + DIFF + OWNER.
- [ ] Never auto-weaken hard safety, sellability or risk gates.
- [ ] Never auto-enable live/wallet/signing.
- [ ] Keep risky mutation/deployment behind explicit approval.

Definition of done:

- Vezir can prepare a validated repair without uncontrolled production mutation.

---

# WORKSTREAM 10 — AI REPORT INGESTION / HAREKÂT SUBAYI BEHAVIOR

Primary owner: Phase 14.

Goal: Vezir consolidates reports from multiple engineering agents and evidence sources.

Inputs may include:

- Codex;
- Copilot;
- CodeRabbit;
- NVIDIA models;
- other approved reviewers;
- GitHub CI;
- VPS tests/runtime.

Tasks:

- [ ] Define common report schema.
- [ ] Record source/model/commit SHA/task/timestamp.
- [ ] Separate findings from opinion.
- [ ] Deduplicate identical findings.
- [ ] Detect conflicting findings.
- [ ] Resolve conflicts using canonical code/tests/runtime evidence where possible.
- [ ] Mark unresolved conflicts explicitly.
- [ ] Rank operational urgency by evidence, not model/provider reputation.
- [ ] Produce one concise operator synthesis.
- [ ] Preserve original report references for audit.

Definition of done:

- operator no longer manually reconciles several AI reports for the same incident.

---

# WORKSTREAM 11 — VEZİR COMMAND CENTER UX

Primary owner: Phase 14.

Goal: evolve Vezir inside the existing single canonical Command Center; never create a second panel.

Planned capabilities:

- [ ] Natural chat.
- [ ] Verified current system status.
- [ ] Active task/checkpoint view.
- [ ] Incoming AI/review reports.
- [ ] Vezir recommendations.
- [ ] Security alerts.
- [ ] Recent learning/outcome findings.
- [ ] Evidence/source disclosure.
- [ ] Approval requests.
- [ ] Model/provider/token/cost status where useful.
- [ ] Compact default view; technical details on demand.
- [ ] No fake data.
- [ ] No duplicate backend/runtime.

Definition of done:

- one canonical panel is sufficient for conversation, evidence, reports, recommendations and approvals.

---

# WORKSTREAM 12 — SAFE AUTOMATION BOUNDARIES

Goal: maximize automation without uncontrolled authority.

Autonomous candidates:

- read/search;
- bounded DB/query evidence;
- log analysis;
- external research;
- report generation;
- recommendation generation;
- controlled test execution;
- read-only code review;
- model benchmark/cost telemetry.

Approval-controlled candidates:

- source/config mutation;
- threshold change;
- service restart;
- commit;
- push;
- deployment;
- persistent DB mutation.

Always denied unless explicitly changed by canonical governance:

- private-key/seed handling;
- wallet signing;
- live order creation;
- live self-enable;
- bypassing hard safety/Risk Gate.

Tasks:

- [ ] Encode capability/permission matrix.
- [ ] Make actions auditable.
- [ ] Ensure model text cannot directly invoke privileged actions.
- [ ] Add permission-escalation tests.
- [ ] Fail closed when approval/state is ambiguous.

Definition of done:

- Vezir is highly autonomous for observation/research/analysis while dangerous actions stay controlled.

---

# WORKSTREAM 13 — LEARNING / MODEL-TRAINING READINESS

Ownership: existing Phase 11/13 for learning semantics; Phase 14 only consumes/operator-presents it. Exact subphase mapping after inventory.

Goal: prepare high-quality data before considering LoRA/QLoRA/distillation.

Collect structured examples:

- task/question;
- bounded evidence;
- root cause;
- accepted/rejected recommendation;
- patch;
- tests;
- runtime result;
- operator acceptance.

Tasks:

- [ ] Define clean evaluation/training event format.
- [ ] Remove secrets/sensitive values.
- [ ] Deduplicate examples.
- [ ] Separate correct fixes from failed attempts.
- [ ] Keep engineering-model learning separate from trading calibration.
- [ ] Accumulate enough high-quality examples before fine-tuning.
- [ ] Evaluate NVIDIA NeMo/QLoRA/distillation only after retrieval/tool/routing is strong.
- [ ] Never create a new architecture tree for training.

Definition of done:

- a clean benchmark/evaluation corpus exists;
- no premature training dependency has been introduced.

---

# WORKSTREAM 14 — CLEANUP / MUTATION CONTROL

Goal: complexity must stay flat or decrease as capability grows.

Tasks:

- [ ] Reference-audit old AI/Vezir/provider code before replacements.
- [ ] Remove superseded executable code after replacement tests pass.
- [ ] Remove stale debug/disposable scripts.
- [ ] Remove stale `.bak` artifacts.
- [ ] Remove duplicate configs/providers/routes.
- [ ] Remove unused test helpers.
- [ ] Preserve historical audit/closure documents as evidence.
- [ ] No second panel.
- [ ] No second Vezir runtime.
- [ ] No duplicate trading/decision pipeline.
- [ ] No unnecessary microservice/Redis/Celery/Kafka layer.
- [ ] No temporary architecture left behind after acceptance.

Definition of done:

- one canonical implementation path remains for each responsibility.

---

# WORKSTREAM 15 — VALIDATION / CLOSURE PROTOCOL

Every implementation slice closes through the existing canonical process.

- [ ] Owner Phase/subphase confirmed.
- [ ] Targeted implementation complete.
- [ ] Targeted tests PASS.
- [ ] Security/authority assertions PASS.
- [ ] Canonical smoke/E2E PASS where relevant.
- [ ] Full regression where scope/risk requires.
- [ ] Compile/static checks PASS.
- [ ] DB integrity where relevant.
- [ ] `git diff --check` PASS.
- [ ] Dead-code/reference audit complete.
- [ ] Second review where meaningful.
- [ ] GitHub merge/seal.
- [ ] VPS clean-state/sync.
- [ ] Runtime acceptance.
- [ ] This tracker updated.
- [ ] PROJECT_STATE updated with current checkpoint.
- [ ] TEST_RESULTS updated with validation evidence.

A task is not complete because code exists; it is complete only after evidence-backed acceptance.

---

# GLOBAL SUCCESS CONDITION

The target is not “more AI code”.

The target is:

```text
Coinoskobi deterministic core
        │
        ├── safe automated PAPER runtime
        ├── bounded local evidence
        │
        └── Vezir operator layer
              │
              ├── conversation + memory
              ├── reports + recommendations
              ├── internal health/security diagnosis
              ├── external adversary research
              ├── code/test repair proposals
              └── multi-model engineering orchestration
                       │
                       ├── local tools first
                       ├── cheap/free models
                       ├── NVIDIA
                       ├── Codex
                       └── premium escalation only when needed
```

All of this remains inside the existing Phase 0–15 architecture and existing owner/subphase rules.

---

# PROGRESS UPDATE TEMPLATE

After each meaningful accepted slice, tick the relevant boxes and append a compact checkpoint:

```text
DATE:
WORKSTREAM:
OWNER PHASE/SUBPHASE:
TASK:
STATUS:
FILES:
TESTS:
RUNTIME:
GITHUB PR/COMMIT:
AUTHORITY CHANGED: NO/YES
DEAD CODE REMOVED:
TOKEN/COST EVIDENCE:
NEXT SAFE STEP:
```

Detailed validation history belongs in `TEST_RESULTS.md`.  
Current production truth belongs in `PROJECT_STATE.md`.  
This file keeps only the active cross-phase work state.

---

# CHANGE LOG

## 2026-09-19 — Active tracker established

- Canonical Phase/subphase mutation-control rules already documented.
- Scope expanded to cover all current discussed work, not only Vezir.
- PAPER recovery closure added as prerequisite.
- Low-token local evidence strategy added.
- GitHub/Codex/NVIDIA/multi-model engineering workflow added.
- Vezir conversation/memory/report/recommendation/security/code-diagnosis scope added.
- External adversary research added.
- Harekât Subayı multi-report synthesis added.
- Training-readiness and cleanup/validation rules added.
- No new Phase/ERA/version architecture created.

**Current next safe step:** close/verify PAPER recovery, then complete WORKSTREAM 02 ownership/subphase/dead-code inventory.
