#!/bin/bash

BASE="/home/lkern/BioconductorPackages"

LOG="$BASE/Syncing/push_failed_investigation.log"
MANIFEST="$BASE/PkgManagement/manifest"
OUT="$BASE/Syncing/push_failure_summary.tsv"

echo -e "Package\tCategory\tManifest" > "$OUT"


awk '
/^Package:/ {
    if (pkg != "") {
        print pkg "\t" category
    }
    pkg=$2
    category="other"
}
/GH001: Large files detected/ {
    category="large_file_error"
}
/GH013|secret|Push cannot contain secrets|Secret scanning/ {
    if (category != "large_file_error")
        category="secret_error"
}
END {
    if (pkg != "")
        print pkg "\t" category
}
' "$LOG" |
while IFS=$'\t' read -r pkg category
do
    manifest="not_found"

    for f in software.txt data-experiment.txt data-annotation.txt workflows.txt
    do
        if grep -qx "Package: $pkg" "$MANIFEST/$f"; then
            manifest="$f"
            break
        fi
    done

    echo -e "$pkg\t$category\t$manifest"

done | sort -k2,2 -k3,3 -k1,1 >> "$OUT"
