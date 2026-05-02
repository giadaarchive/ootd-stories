#!/usr/bin/env bash
# Runs when Claude stops. Auto-commits any uncommitted work, then reminds to push.

REPO=$(git rev-parse --show-toplevel 2>/dev/null)
[ -z "$REPO" ] && exit 0
cd "$REPO" || exit 0

# ── Auto-commit uncommitted changes ───────────────────────────────────────────
HAS_STAGED=$(git diff --cached --quiet; echo $?)
HAS_UNSTAGED=$(git diff --quiet; echo $?)
HAS_UNTRACKED=$(git ls-files --others --exclude-standard | wc -l | tr -d ' ')

if [ "$HAS_STAGED" -ne 0 ] || [ "$HAS_UNSTAGED" -ne 0 ] || [ "$HAS_UNTRACKED" -gt 0 ]; then
    git add .
    BRANCH=$(git branch --show-current)
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
    git commit -m "checkpoint: $TIMESTAMP [$BRANCH]

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>" 2>/dev/null && \
        echo "[stop-hook] Committed uncommitted changes."
fi

# ── Remind to push if unpushed commits exist ───────────────────────────────────
UNPUSHED=$(git log @{u}.. --oneline 2>/dev/null | wc -l | tr -d ' ')
if [ "$UNPUSHED" -gt 0 ]; then
    echo ""
    echo "  $UNPUSHED unpushed commit(s) on $(git branch --show-current)."
    echo "  Push when ready:  git push origin main"
    echo ""
fi
