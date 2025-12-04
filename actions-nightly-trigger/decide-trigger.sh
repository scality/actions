#!/bin/bash
# Decision logic for smart nightly trigger
# Outputs: writes trigger decision to result.txt

set -e

# Input parameters
LAST_COMMIT_TIME="${LAST_COMMIT_TIME:-0}"
STATUS="${STATUS:-not_found}"
DAYS_SINCE="${DAYS_SINCE:-999}"
RUN_COUNT="${RUN_COUNT:-0}"
LAST_RUN_CONCLUSION="${LAST_RUN_CONCLUSION:-not_found}"
LAST_RUN_STATUS="${LAST_RUN_STATUS:-not_found}"
MAX_RETRIES="${MAX_RETRIES:-0}"

trigger="false"
reason="No trigger conditions met"

# Calculate if last commit is within 24 hours
current_time=$(date +%s)
time_diff=$((current_time - LAST_COMMIT_TIME))
hours_ago=$((time_diff / 3600))

# Priority 1: Restart if last run on last commit failed and under max restarts
if [ "$MAX_RETRIES" -gt 0 ]; then
    # Check if last run on commit failed
    if [ "$LAST_RUN_CONCLUSION" = "failure" ] || [ "$LAST_RUN_CONCLUSION" = "timed_out" ] || [ "$LAST_RUN_CONCLUSION" = "cancelled" ]; then
        # Check if we haven't exceeded max restarts
        if [ "$RUN_COUNT" -lt "$MAX_RETRIES" ]; then
            trigger="true"
            reason="Last run failed (${LAST_RUN_CONCLUSION}), restarting ($RUN_COUNT/$MAX_RETRIES)"
            echo "🔄 $reason"
        else
            echo "⏭️ Max restarts reached ($RUN_COUNT/$MAX_RETRIES), last run: ${LAST_RUN_CONCLUSION}"
        fi
    elif [ "$LAST_RUN_CONCLUSION" = "success" ]; then
        echo "✅ Last run on commit succeeded, no restart needed"
    fi
fi

# Priority 2: Trigger if last commit is within 24 hours (and not already succeeded)
if [ "$trigger" = "false" ] && [ "$LAST_COMMIT_TIME" -gt 0 ] && [ $time_diff -le 86400 ]; then
    # Only trigger if no successful run exists on this commit
    if [ "$LAST_RUN_CONCLUSION" != "success" ]; then
        trigger="true"
        reason="Last commit was ${hours_ago}h ago (within 24h)"
        echo "✨ $reason"
    else
        echo "✅ Last commit was ${hours_ago}h ago but already has successful run"
    fi

# Priority 3: Weekly health check (modulo 7 ensures only once per week)
elif [ "$trigger" = "false" ] && [ "$STATUS" != "not_found" ] && [ "$DAYS_SINCE" -gt 0 ] && [ $(($DAYS_SINCE % 7)) -eq 0 ]; then
    trigger="true"
    reason="Weekly health check ($DAYS_SINCE days since last run)"
    echo "🏥 $reason"

# Default: Skip
elif [ "$trigger" = "false" ]; then
    echo "⏭️ Skipping nightly - $reason"
    echo "   - Last commit: ${hours_ago}h ago"
    echo "   - Days since last run: $DAYS_SINCE"
fi

# Write results to result.txt
cat > result.txt <<EOF
trigger=$trigger
reason=$reason
EOF
