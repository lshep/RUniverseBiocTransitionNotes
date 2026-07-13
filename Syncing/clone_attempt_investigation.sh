LOGFILE="clone_attempt2.log"

cat "/home/lkern/BioconductorPackages/Syncing/clone_failed.txt" |
while read -r pkg; do
    cd "$BASE" || exit 1

    if [ -d "$pkg.git" ]; then
        echo "$pkg: local repo already exists" | tee -a "$LOGFILE"
        continue
    fi

    echo "===== Cloning $pkg =====" | tee -a "$LOGFILE"

    git clone --mirror --verbose \
        "git@git.bioconductor.org:packages/$pkg.git" \
        >>"$LOGFILE" 2>&1

    if [ $? -ne 0 ]; then
        echo "$pkg: clone FAILED" | tee -a "$LOGFILE"
    else
        echo "$pkg: clone succeeded" | tee -a "$LOGFILE"
    fi
done



##################################################

#!/bin/bash

set -e

BASE="/home/lkern/BioconductorPackages/PkgManagement/manifest"
cd "$BASE"

files=(
    "software.txt"
    "data-experiment.txt"
    "data-annotation.txt"
    "workflows.txt"
)

OUTPUT="/home/lkern/BioconductorPackages/Syncing/clone_failed_investigation.log"
: > "$OUTPUT"

# Build ordered branch list:
#   devel
#   RELEASE_* (newest -> oldest)
branches=$(
{
    git for-each-ref --format='%(refname:short)' refs/heads/ refs/remotes/origin/ |
        grep -E '(^|/)devel$'

    git for-each-ref --format='%(refname:short)' refs/heads/ refs/remotes/origin/ |
        grep 'RELEASE_' |
        sort -Vr
} | awk '!seen[$0]++'
)

while read -r pkg; do
    [ -z "$pkg" ] && continue

    found=0

    while read -r branch; do
        for file in "${files[@]}"; do
            if git show "$branch:$file" 2>/dev/null | grep -Fxq "Package: $pkg"; then
                printf "%-40s %-30s %s\n" "$pkg" "$branch" "$file" | tee -a "$OUTPUT"
                found=1
                break 2
            fi
        done
    done <<< "$branches"

    if [ $found -eq 0 ]; then
        printf "%-40s NOT FOUND\n" "$pkg" | tee -a "$OUTPUT"
    fi

done < /home/lkern/BioconductorPackages/Syncing/clone_failed.txt

echo
echo "Results written to $OUTPUT"

