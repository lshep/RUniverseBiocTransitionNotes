
## unset GITHUB_TOKEN
## unset GH_TOKEN
## gh auth logout
## gh auth login 



#!/bin/bash

set -e

BASE="/home/lkern/BioconductorPackages/PkgManagement/manifest"
cd "$BASE"

INPUT_FILES=(
    "all_software.txt"
    "all_data-experiment.txt"
    "all_data-annotation.txt"
    "all_workflows.txt"
    "all_books.txt"
)

MANIFEST_FILES=(
    "software.txt"
    "data-experiment.txt"
    "data-annotation.txt"
    "workflows.txt"
    "books.txt"
)

OUTPUT="/home/lkern/BioconductorPackages/Syncing/packages_deprecated.txt"
: > "$OUTPUT"

# Build unique package list
cat "${INPUT_FILES[@]}" | sort -u | while read -r pkg; do
    [ -z "$pkg" ] && continue

    found=0

    for branch in devel origin/RELEASE_3_23; do
        for manifest in "${MANIFEST_FILES[@]}"; do
            if git show "$branch:$manifest" 2>/dev/null | grep -Fxq "Package: $pkg"; then
                found=1
                break 2
            fi
        done
    done

    if [ $found -eq 0 ]; then
        echo "$pkg" | tee -a "$OUTPUT"
    fi
done

echo
echo "Deprecated package list written to $OUTPUT"





topic="bioc-deprecated"
cat "/home/lkern/BioconductorPackages/Syncing/packages_deprecated.txt" |
while read pkg; do
	gh repo edit "bioconductor-source/$pkg" --add-topic "$topic"
done
