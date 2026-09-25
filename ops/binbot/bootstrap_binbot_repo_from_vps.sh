#!/usr/bin/env bash
set -euo pipefail

OWNER="anketci54-coder"
NAME="binbot"
REMOTE="$OWNER/$NAME"

TR="/root/bintrbot"
GLOBAL="/root/binbot/global"
REPO="/root/binbot/repo"
TS="$(date -u +%Y%m%dT%H%M%SZ)"

echo "=== PREFLIGHT ==="
command -v gh >/dev/null
command -v git >/dev/null
gh auth status >/dev/null 2>&1
test -d "$TR"
test -d "$GLOBAL"

echo "=== REPO ==="
if ! gh repo view "$REMOTE" >/dev/null 2>&1; then
  gh repo create "$REMOTE" --private --description "BINBOT - Binance TR and Binance Global market data intelligence platform"
  echo "CREATED=$REMOTE"
else
  echo "EXISTS=$REMOTE"
fi

mkdir -p /root/binbot

if [ -e "$REPO" ] && [ ! -d "$REPO/.git" ]; then
  mv "$REPO" "$REPO.prebootstrap.$TS.bak"
fi

if [ ! -d "$REPO/.git" ]; then
  gh repo clone "$REMOTE" "$REPO"
fi

cd "$REPO"
git fetch origin || true

if git show-ref --verify --quiet refs/remotes/origin/main; then
  git checkout -B main origin/main
else
  git checkout -B main
fi

rm -rf tr global ops
mkdir -p \
  tr/app tr/config tr/scripts tr/tests tr/docs \
  global/app global/config global/scripts global/tests global/docs

copy_tree() {
  src="$1"
  dst="$2"
  [ -d "$src" ] || return 0
  mkdir -p "$dst"
  (
    cd "$src"
    find . -type f \
      ! -path '*/__pycache__/*' \
      ! -name '*.pyc' \
      ! -name '*.pyo' \
      ! -name '.env' \
      ! -name '.env.*' \
      ! -iname '*secret*' \
      ! -iname '*credential*' \
      ! -iname '*.key' \
      ! -iname '*.pem' \
      ! -iname '*.parquet' \
      ! -iname '*.jsonl' \
      ! -iname '*.jsonl.zst' \
      ! -iname '*.zst' \
      ! -iname '*.sqlite' \
      ! -iname '*.sqlite3' \
      ! -iname '*.db' \
      -print0
  ) | while IFS= read -r -d '' f; do
    mkdir -p "$dst/$(dirname "$f")"
    cp -a "$src/$f" "$dst/$f"
  done
}

echo "=== COPY TR CODE ==="
copy_tree "$TR/app" "$REPO/tr/app"
copy_tree "$TR/config" "$REPO/tr/config"
copy_tree "$TR/tests" "$REPO/tr/tests"
copy_tree "$TR/docs" "$REPO/tr/docs"

find "$TR" -maxdepth 1 -type f -name '*.sh' -print0 2>/dev/null |
while IFS= read -r -d '' f; do
  cp -a "$f" "$REPO/tr/scripts/"
done

echo "=== COPY GLOBAL CODE ==="
copy_tree "$GLOBAL/app" "$REPO/global/app"
copy_tree "$GLOBAL/config" "$REPO/global/config"
copy_tree "$GLOBAL/tests" "$REPO/global/tests"
copy_tree "$GLOBAL/docs" "$REPO/global/docs"
[ -f "$GLOBAL/status.sh" ] && cp -a "$GLOBAL/status.sh" "$REPO/global/scripts/status.sh"

cat > "$REPO/.gitignore" <<'EOF'
# Runtime datasets/state remain on VPS
**/data/
**/state/
**/logs/
**/cache/
**/__pycache__/

# Large/raw data
*.parquet
*.jsonl
*.jsonl.zst
*.zst
*.sqlite
*.sqlite3
*.db
*.csv.gz

# Runtime/temp
*.pyc
*.pyo
*.log
*.tmp
*.bak
*.pid
nohup.out

# Secrets
.env
.env.*
*.pem
*.key
*secret*
*credential*
EOF

cat > "$REPO/README.md" <<'EOF'
# BINBOT

BINBOT is split into two isolated venue trees:

- `tr/` — Binance TR code
- `global/` — Binance Global code

## Data policy

GitHub stores source code, non-secret configuration, scripts, tests, and docs only.

Datasets remain on the VPS and are intentionally excluded from Git:

- historical Parquet
- live raw market data
- order-book/depth data
- aggTrades data
- runtime state/checkpoints
- quality history
- caches/backups

Current runtime paths:

- TR: `/root/bintrbot/`
- GLOBAL: `/root/binbot/global/`

TR will later be migrated safely to `/root/binbot/tr/` after active runtime work is closed.
EOF

echo "=== SAFETY GUARD ==="
git add -A

BAD="$(git diff --cached --name-only | grep -Ei '(^|/)(data|state|logs|cache)/|\.parquet$|\.jsonl($|\.)|\.zst$|\.sqlite3?$|\.db$|(^|/)\.env($|\.)' || true)"
if [ -n "$BAD" ]; then
  echo "ABORT_PROHIBITED_FILES"
  echo "$BAD"
  git reset
  exit 10
fi

while IFS= read -r f; do
  [ -f "$f" ] || continue
  size="$(stat -c%s "$f")"
  if [ "$size" -gt 5242880 ]; then
    echo "ABORT_LARGE_FILE=$f bytes=$size"
    git reset
    exit 11
  fi
done < <(git diff --cached --name-only)

echo "DATASET_GITHUB_GUARD=PASS"

git config user.name "anketci54-coder"
git config user.email "anketci54-coder@users.noreply.github.com"

if git diff --cached --quiet; then
  echo "NO_NEW_CHANGES"
else
  git commit -m "Bootstrap BINBOT source tree"
fi

git push -u origin main

echo "=== FINAL ==="
echo "GITHUB_REPO=https://github.com/$REMOTE"
echo "LOCAL_REPO=$REPO"
echo "DATASETS_REMAIN_ON_VPS=YES"
git status --short
git log -1 --oneline
