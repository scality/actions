#!/bin/bash
# Test script for decide-trigger.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DECIDE_SCRIPT="$SCRIPT_DIR/decide-trigger.sh"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

test_count=0
pass_count=0
fail_count=0

# Helper function to run a test
run_test() {
    local test_name="$1"
    local expected_exit="$2"
    local expected_trigger="$3"

    test_count=$((test_count + 1))
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "Test #$test_count: $test_name"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Run the script
    cd "$SCRIPT_DIR"
    if $DECIDE_SCRIPT; then
        actual_exit=0
    else
        actual_exit=1
    fi

    # Check result.txt exists
    if [ ! -f result.txt ]; then
        echo -e "${RED}✗ FAIL: result.txt not created${NC}"
        fail_count=$((fail_count + 1))
        return
    fi

    # Display result.txt
    echo "Result file contents:"
    cat result.txt

    # Parse result
    actual_trigger=$(grep "^trigger=" result.txt | cut -d= -f2)

    # Verify exit code
    if [ "$actual_exit" != "$expected_exit" ]; then
        echo -e "${RED}✗ FAIL: Expected exit code $expected_exit, got $actual_exit${NC}"
        fail_count=$((fail_count + 1))
        return
    fi

    # Verify trigger value
    if [ "$actual_trigger" != "$expected_trigger" ]; then
        echo -e "${RED}✗ FAIL: Expected trigger=$expected_trigger, got trigger=$actual_trigger${NC}"
        fail_count=$((fail_count + 1))
        return
    fi

    echo -e "${GREEN}✓ PASS${NC}"
    pass_count=$((pass_count + 1))

    # Cleanup
    rm -f result.txt
}

echo "═══════════════════════════════════════════"
echo "Testing decide-trigger.sh"
echo "═══════════════════════════════════════════"

# Get current timestamp for tests
current_time=$(date +%s)

# Test 1: Recent commit (5 hours ago, should trigger)
export LAST_COMMIT_TIME=$((current_time - 18000))  # 5 hours ago
export STATUS="not_found"
export DAYS_SINCE=999
run_test "Last commit 5 hours ago (within 24h)" 0 "true"

# Test 2: Old commit (30 hours ago, should not trigger by commit)
export LAST_COMMIT_TIME=$((current_time - 108000))  # 30 hours ago
export STATUS="completed"
export DAYS_SINCE=7
run_test "Weekly health check at 7 days" 0 "true"

# Test 3: Weekly health check (14 days)
export DAYS_SINCE=14
run_test "Weekly health check at 14 days" 0 "true"

# Test 4: No trigger conditions (5 days, old commit)
export LAST_COMMIT_TIME=$((current_time - 172800))  # 48 hours ago
export DAYS_SINCE=5
run_test "No trigger conditions (5 days since last run)" 0 "false"

# Test 5: No trigger conditions (3 days, old commit)
export STATUS="completed"
export DAYS_SINCE=3
run_test "No trigger conditions (old commit, 3 days)" 0 "false"

# Test 6: Edge case - 0 days since last run
export DAYS_SINCE=0
run_test "Edge case: 0 days since last run" 0 "false"

# Test 7: Status not found, old commit
export STATUS="not_found"
export DAYS_SINCE=999
run_test "Status not found, old commit" 0 "false"

# Test 8: Restart on failure - first failure (1 run, max 3)
export LAST_COMMIT_TIME=$((current_time - 172800))  # 48 hours ago (old commit)
export STATUS="completed"
export DAYS_SINCE=1
export RUN_COUNT=1
export LAST_RUN_CONCLUSION="failure"
export LAST_RUN_STATUS="completed"
export MAX_RETRIES=3
run_test "Restart on failure - first failure (1/3)" 0 "true"

# Test 9: Restart on failure - max restarts reached
export RUN_COUNT=3
export LAST_RUN_CONCLUSION="failure"
export MAX_RETRIES=3
run_test "Max restarts reached (3/3)" 0 "false"

# Test 10: No restart - last run succeeded
export RUN_COUNT=2
export LAST_RUN_CONCLUSION="success"
export MAX_RETRIES=3
run_test "Last run succeeded, no restart needed" 0 "false"

# Test 11: Restart on timeout
export RUN_COUNT=1
export LAST_RUN_CONCLUSION="timed_out"
export MAX_RETRIES=3
run_test "Restart on timeout (1/3)" 0 "true"

# Test 12: Restart on cancelled
export RUN_COUNT=2
export LAST_RUN_CONCLUSION="cancelled"
export MAX_RETRIES=3
run_test "Restart on cancelled (2/3)" 0 "true"

# Test 13: Max retries disabled (0)
export RUN_COUNT=1
export LAST_RUN_CONCLUSION="failure"
export MAX_RETRIES=0
run_test "Max retries disabled (MAX_RETRIES=0)" 0 "false"

# Test 14: Recent commit with successful run - should not trigger
export LAST_COMMIT_TIME=$((current_time - 18000))  # 5 hours ago
export RUN_COUNT=1
export LAST_RUN_CONCLUSION="success"
export MAX_RETRIES=3
run_test "Recent commit with successful run" 0 "false"

# Test 15: Weekly health check takes priority even when max restarts exceeded
export LAST_COMMIT_TIME=$((current_time - 172800))  # 48 hours ago (old commit)
export STATUS="completed"
export DAYS_SINCE=7
export RUN_COUNT=3
export LAST_RUN_CONCLUSION="failure"
export MAX_RETRIES=3
run_test "Weekly health check with max restarts reached (7 days)" 0 "true"

# Summary
echo ""
echo "═══════════════════════════════════════════"
echo "Test Summary"
echo "═══════════════════════════════════════════"
echo "Total tests: $test_count"
echo -e "${GREEN}Passed: $pass_count${NC}"
if [ $fail_count -gt 0 ]; then
    echo -e "${RED}Failed: $fail_count${NC}"
    exit 1
else
    echo "All tests passed! ✓"
    exit 0
fi
