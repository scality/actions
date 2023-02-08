#!/bin/bash

# Archive all cores corresponding to a given set of core_patterns to
# $artifacts_output_directory/cores.
# When possible, the binary that generated the core is also archived, and
# backtraces are generated and archived.
#
# Example:
# ./archive_cores.sh $ARTIFACT_DIR ./core.* /tmp/core.*

if [ "$#" -lt 2 ]; then
    echo "usage: $0 <artifacts_output_directory> <core_patterns...>"
    exit 1
fi

ARTIFACTS="$1"
EXPECTED_CRASHES="$2"
shift
shift
CORE_PATTERNS="$@"

OUTPUT_DIR="${ARTIFACTS}/cores"

CORES="$(ls -dUN $CORE_PATTERNS 2> /dev/null)"

is_expected_crash()
{
    local bt_full="$1"
    local bin="$2"

    for match in $EXPECTED_CRASHES; do
        if grep -q "$match" "$bt_full"; then
            echo "Known and expected crash of $bin: $match, skipping"
            return 0
        fi
    done

    # Externally sent SIGSEV to test biz* daemons behavior
    if grep '^#3  <signal handler called>' -A2 "$bt_full" | grep -q '^#4 .*\(epoll_wait\|libpthread\)'; then
        echo "Known and expected crash of $bin: daemon externally killed with SIGSEGV, skipping"
        return 0
    fi

    return 1
}

# Retrieve the path of the binary from a core
get_bin_path()
{
    local core="$1"
    local bin=

    # First try: get the core name with file
    bin="$(file "$core" | grep 'execfn: ' | sed "s/.*execfn: '\([^']\+\)'.*/\1/")"
    test -n "$bin" && bin="$(which "$bin")"

    # This may fail if there are too many section headers in the core, newer
    # versions of `file` can deal with this
    if [ ! -e "$bin" ]; then
        bin="$(file -Pelf_phnum=20000 "$core" 2>/dev/null \
               | grep 'execfn: ' \
               | sed "s/.*execfn: '\([^']\+\)'.*/\1/")"
        test -n "$bin" && bin="$(which "$bin")"
    fi

    # Last try with gdb
    if [ ! -e "$bin" ]; then
        bin="$(gdb -n --batch "$core" 2>/dev/null \
               | grep "^Core was generated by" \
               | sed "s/^Core was generated by \`\([^ \`']\+\).*/\1/")"
        test -n "$bin" && bin="$(which "$bin")"
    fi

    if [ -e "$bin" ]; then
        echo "$bin"
        return 0
    else
        return 1
    fi
}

if [ -z "$CORES" ]; then
    echo "no core to collect"
    exit 0
fi

mkdir -p "${OUTPUT_DIR}"
for core in $CORES; do
    if ! file "$core" | grep -q 'core file'; then
        echo "$core is not a core file"
        file "$core"
        continue
    fi

    core_name="$(basename "$core")"
    bin="$(get_bin_path "$core")"

    echo "archive core '$core' for binary '$bin' to $OUTPUT_DIR"

    if [ ! -e "$bin" ]; then
        echo "failed to parse binary path or does not exist, got: '$bin'"
        file "$core"
    else
        # Generate backtraces
        core_name="$(basename "$bin")-$(basename "$core")"
        prefix="${OUTPUT_DIR}/$core_name-backtrace"
        bt_full="$prefix-full.txt"
        bt_all="$prefix-all.txt"

        gdb -batch -ex 'bt full' "$bin" "$core" > "$bt_full"

        # Known and expected crashes
        if is_expected_crash $bt_full $bin; then
            rm "$bt_full"
            continue
        fi

        gdb -batch -ex 'thread apply all bt' "$bin" "$core" > "$bt_all"

        # Archive binary
        cp "$bin" "$OUTPUT_DIR"
    fi

    # Archive core
    tar -czSf "${OUTPUT_DIR}/$core_name.tar.gz" "$core"
done
