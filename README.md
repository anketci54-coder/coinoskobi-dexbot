# Coinoskobi DEX Bot

Modüler Python tabanlı DEX alım-satım platformu.

İlk hedefler:

- BNB Chain
- PancakeSwap
- Güvenli cüzdan yönetimi
- Paper Trading
- Risk Motoru
- Modüler mimari

Canlı işlem özelliği yalnızca gerekli testler tamamlandıktan sonra etkinleştirilecektir.
# 🚀 Coinoskobi DexBot

> **Professional Modular DEX Decision Support & Paper Trading Platform**

---

![Python](https://img.shields.io/badge/Python-3.13-blue)
![SQLite](https://img.shields.io/badge/Database-SQLite-green)
![Status](https://img.shields.io/badge/Status-Active-success)
![Roadmap](https://img.shields.io/badge/Roadmap-Phase%200%20%E2%86%92%20Phase%2015-orange)
![PaperTrading](https://img.shields.io/badge/Trading-Paper%20Only-yellow)

---

# Overview

Coinoskobi is a professional modular Decision Support Platform for decentralized exchanges (DEX).

The system is designed to discover trading opportunities, evaluate market quality, analyze risks and validate trading strategies through paper trading before any live execution.

The project prioritizes **decision quality over trading frequency**.

---

# Vision

Coinoskobi aims to become a complete trading intelligence platform capable of:

- Discovering new opportunities
- Evaluating liquidity quality
- Analyzing smart contracts
- Measuring trading risks
- Simulating trades
- Learning from historical outcomes
- Supporting human decision making

Live trading is intentionally the final milestone of the project.

---

# Core Principles

- Simplicity
- Readability
- Maintainability
- Modularity
- Security
- Paper-first development
- Evidence-based decision making

---

# Current Architecture

```text
Scanner
    │
    ▼
Gecko Cache
    │
    ▼
Candidate Filter
    │
    ▼
Token Analyzer
    │
    ▼
Pair Analyzer
    │
    ▼
Risk Engine
    │
    ▼
Strategy Engine
    │
    ▼
Paper Trading
    │
    ▼
Portfolio
    │
    ▼
API
```

---

# Current Modules

## Scanner

- GeckoTerminal Scanner
- Candidate Discovery
- Cache Refresh

---

## Cache

- SQLite Cache
- Market Snapshot Storage

---

## Filter

- Liquidity Filter
- Volume Filter
- DEX Filter

---

## Analyzer

- ERC20 Analysis
- Pair Analysis
- Contract Analysis

---

## Risk Engine

- Contract Risk
- Trading Risk

---

## Strategy

Current decisions:

- BUY
- WATCH
- REJECT

Future versions will include:

- Decision Score
- Confidence Score
- Multi-factor Evaluation

---

## Paper Trading

Current capabilities:

- Position Tracking
- ROI Calculation
- Take Profit
- Stop Loss
- Trailing Stop
- Portfolio Statistics

---

# Repository Structure

```text
app/

├── analyzer/
├── api/
├── cache/
├── chains/
├── config/
├── dex/
├── filter/
├── paper/
├── risk/
├── scanner/
└── strategy/

data/

main.py
```

---

# Documentation

The project is governed by the following documents:

- CONSTITUTION.md
- ROADMAP.md
- PROJECT_STATUS.md
- CHANGELOG.md
- ARCHITECTURE.md
- CONTRIBUTING.md
- roadmap.json

---

# Development Workflow

Every feature follows the same lifecycle.

```text
Roadmap

↓

Planning

↓

Implementation

↓

Testing

↓

Review

↓

Commit

↓

Push

↓

Next Phase
```

---

# Roadmap

The official roadmap consists of:

- Phase 0
- Phase 1
- Phase 2
- Phase 3
- Phase 4
- Phase 5
- Phase 6
- Phase 7
- Phase 8
- Phase 9
- Phase 10
- Phase 11
- Phase 12
- Phase 13
- Phase 14
- Phase 15

## Important

**Phase 15 is the final roadmap phase.**

No Phase 16 will ever be created.

Future work continues through:

- Releases
- Milestones
- Sprints
- Hotfixes
- Patches

---

# Development Rules

- One responsibility per module
- No dead code
- No temporary patches
- No duplicated logic
- Small commits
- Compile before commit
- Clean repository
- Stable main branch

---

# Security

- Private keys are never committed.
- `.env` is ignored.
- Live trading is disabled by default.
- Paper Trading is mandatory before Live Trading.

---

# Technologies

- Python 3
- SQLite
- Web3.py
- FastAPI
- GeckoTerminal API

---

# Current Status

**Project Status**

🟢 Active Development

Current Branch:

`main`

Current Milestone:

**Phase 0 Completed**

Next Objective:

**Phase 1 — Scanner Stabilization**

---

# License

Private Repository

All Rights Reserved.

---

# Coinoskobi

**Professional Modular DEX Decision Support Platform**
