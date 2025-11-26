#!/bin/bash
# Decision logic for smart nightly trigger
# Returns: 0 if should trigger, 1 if should skip
# Outputs: writes trigger decision to result.txt

set -e

# Input parameters
LAST_COMMIT_TIME="${LAST_COMMIT_TIME:-0}"
STATUS="${STATUS:-not_found}"
DAYS_SINCE="${DAYS_SINCE:-999}"

trigger="false"
reason="No trigger conditions met"

# Calculate if last commit is within 24 hours
current_time=$(date +%s)
time_diff=$((current_time - LAST_COMMIT_TIME))
hours_ago=$((time_diff / 3600))

# Priority 1: Trigger if last commit is within 24 hours
if [ "$LAST_COMMIT_TIME" -gt 0 ] && [ $time_diff -le 86400 ]; then
    trigger="true"
    reason="Last commit was ${hours_ago}h ago (within 24h)"
    echo "✨ $reason"

# Priority 2: Weekly health check (modulo 7 ensures only once per week)
elif [ "$STATUS" != "not_found" ] && [ "$DAYS_SINCE" -gt 0 ] && [ $(($DAYS_SINCE % 7)) -eq 0 ]; then
    trigger="true"
    reason="Weekly health check ($DAYS_SINCE days since last run)"
    echo "🏥 $reason"

# Default: Skip
else
    echo "⏭️ Skipping nightly - $reason"
    echo "   - Last commit: ${hours_ago}h ago"
    echo "   - Days since last run: $DAYS_SINCE"
fi

# Write results to result.txt
cat > result.txt <<EOF
trigger=$trigger
reason=$reason
EOF

# Return exit code based on trigger decision
if [ "$trigger" = "true" ]; then
    exit 0  # Should trigger
else
    exit 1  # Should skip
fi
