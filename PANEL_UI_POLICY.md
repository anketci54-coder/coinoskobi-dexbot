# COINOSKOBI PANEL UI POLICY

## IMMUTABLE APPROVED WINDOW RULE

This policy is mandatory for every Coinoskobi panel update.

### CORE RULE

APPROVED WINDOWS NEVER CHANGE.

A locked window may change only when the user explicitly unlocks
that exact window.

## Approval lifecycle

Every new panel window starts as UNLOCKED.

Required flow:

TARGET
-> BACKUP
-> TARGETED UPDATE
-> TEST
-> PANEL SERVICE RESTART
-> HTTP / HEALTH CHECK
-> USER BROWSER REVIEW
-> EXPLICIT USER APPROVAL
-> LOCK

Automated tests do not constitute visual approval.

The user must inspect the real running panel before a window
becomes locked.

## Locked windows

After explicit approval, the window receives a stable LOCK_ID.

Its source must use boundaries such as:

COINOSKOBI_LOCK_BEGIN:<LOCK_ID>

COINOSKOBI_LOCK_END:<LOCK_ID>

The protected source block SHA256 must be recorded.

Before every unrelated UI update:

1. verify every locked block exists;
2. calculate its SHA256;
3. compare it with the approved SHA256.

After the update:

1. calculate locked block SHA256 again;
2. verify it is unchanged.

Any unexpected difference is:

FAIL / STOP

## Targeted updates only

After the first window is locked:

- full-page replacement is forbidden;
- whole UI replacement is forbidden;
- unrelated locked windows must not be edited;
- only the explicitly targeted unlocked window may change.

A later feature must be added through its own target region.

## Rejected updates

If the user rejects a proposed window, only that unlocked target
may be edited again.

Previously approved windows remain unchanged.

## Browser review requirement

Every visible update must be deployed to the canonical panel
runtime so the user can inspect it from the actual panel page.

No visible UI window is considered approved until the user says
it is approved.

## Backend safety boundary

A panel UI update has no implicit authority to modify:

- strategy logic;
- API contracts;
- paper accounting;
- database schema or data;
- risk gates;
- execution authority;
- live trading;
- wallet access;
- signing authority.

Those require their own explicit scope.

## Current canonical runtime

Application:
app.api.panel:app

Port:
8098

Paper generation:
PAPER_10K_V2

Starting paper capital:
10000 USDT

Legacy panel 8096:
RETIRED

Live trading:
DISABLED

Wallet authority:
DISABLED

Signing authority:
DISABLED
