# cat *detected* | grep "push" | sed 's/: push failed//' > push_failed.txt
############################################################

## unset GITHUB_TOKEN
## unset GH_TOKEN
## gh auth logout
## gh auth login 

#!/bin/bash

SAFE_SLEEP=1.2
safe_sleep() {
    sleep "$SAFE_SLEEP"
}

BASE="/home/lkern/BioconductorPackages/Syncing"
INPUT="$BASE/push_failed.txt"
LOG="$BASE/push_failed_investigation.log"

mkdir -p "$BASE"

echo "===================================================" | tee "$LOG"
echo "Push Failure Investigation" | tee -a "$LOG"
echo "Started: $(date)" | tee -a "$LOG"
echo "===================================================" | tee -a "$LOG"
echo | tee -a "$LOG"

while read -r pkg; do

    [ -z "$pkg" ] && continue

    echo | tee -a "$LOG"
    echo "###################################################" | tee -a "$LOG"
    echo "Package: $pkg" | tee -a "$LOG"
    echo "Time: $(date)" | tee -a "$LOG"
    echo "###################################################" | tee -a "$LOG"

    cd "$BASE" || exit 1

    rm -rf "$pkg.git"

    echo "[CLONE]" | tee -a "$LOG"
    if ! git clone --mirror "git@git.bioconductor.org:packages/$pkg.git" \
        >>"$LOG" 2>&1; then
        echo "[FAILED] clone failed" | tee -a "$LOG"
        rm -rf "$BASE/$pkg.git"
        continue
    fi

    cd "$pkg.git" || {
        echo "[FAILED] could not enter mirror" | tee -a "$LOG"
        rm -rf "$BASE/$pkg.git"
        continue
    }

    git remote set-url origin "git@github.com:bioconductor-source/$pkg.git"

    safe_sleep

    echo "[PUSH]" | tee -a "$LOG"
    git push --mirror >>"$LOG" 2>&1
    rc=$?

    echo | tee -a "$LOG"
    echo "[EXIT CODE] $rc" | tee -a "$LOG"

    cd "$BASE" || exit 1
    rm -rf "$BASE/$pkg.git"

done < "$INPUT"

echo | tee -a "$LOG"
echo "===================================================" | tee -a "$LOG"
echo "Finished: $(date)" | tee -a "$LOG"
echo "===================================================" | tee -a "$LOG"
