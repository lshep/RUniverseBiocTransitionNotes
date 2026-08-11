## Set of all packages 
set -e
BASE="/home/lkern/BioconductorPackages/PkgManagement/manifest"
files=("software.txt" "data-experiment.txt" "data-annotation.txt" "workflows.txt" "books.txt")
declare -A OUTFILES=(
  ["software.txt"]="all_software.txt"
  ["data-experiment.txt"]="all_data-experiment.txt"
  ["data-annotation.txt"]="all_data-annotation.txt"
  ["workflows.txt"]="all_workflows.txt"
  ["books.txt"]="all_books.txt"
)
git fetch --all --prune
for file in "${files[@]}"; do
    # IMPORTANT FIX: include BOTH local + remote branches
    git for-each-ref \
        --format='%(refname:short)' \
        refs/heads/ refs/remotes/origin/ |
    while read branch; do
        git show "$branch:$file" 2>/dev/null |
        awk -v f="$file" '
            /^Package:/ {
                gsub(/^Package:[[:space:]]*/, "", $0);
                print $0 "|" f
            }
        '
    done |
    sort -u |
    awk -F'|' '
    {
        pkg=$1; file=$2;
        seen[pkg][file]=1;
    }
    END {
        for (p in seen) {
            print p > "/dev/stderr";
            n=0;
            for (f in seen[p]) n++;
            if (n >= 1) {
                print p > out;
            }
        }
    }' out="${OUTFILES[$file]}" > /dev/null
done


## check for dupliates (package changed types)
files=("all_software.txt" "all_data-experiment.txt" "all_data-annotation.txt" "all_workflows.txt" "all_books.txt")
tmp=$(mktemp)
for f in "${files[@]}"; do
    awk -v file="$f" '{print $0 "|" file}' "$f"
done > "$tmp"
awk -F'|' '
{
    pkg=$1; file=$2;
    seen[pkg][file]=1;
}
END {
    for (p in seen) {
        n=0;
        for (f in seen[p]) n++;
        if (n > 1) {
            print p;
            for (f in seen[p]) print "   " f;
            print "";
        }
    }
}' "$tmp" > duplicates_detected.txt
rm -f "$tmp"

## duplicates_detected.txt should be empty
## If not pick appropriate repo and delete from additional

# cat duplicates_detected.txt 
# BioPlex
#    all_software.txt
# *   all_data-experiment.txt

# SNAData
#    all_software.txt
# *   all_data-experiment.txt

# affydata
#    all_software.txt
# *   all_data-experiment.txt

# BgeeCall
# *   all_software.txt
#    all_workflows.txt



## create active package list
set -e

BASE="/home/lkern/BioconductorPackages/PkgManagement/manifest"
cd "$BASE"

files=("software.txt" "data-experiment.txt" "data-annotation.txt" "workflows.txt" "books.txt")

git fetch --all --prune

for branch in devel RELEASE_3_23; do
    for file in "${files[@]}"; do
        git show "$branch:$file" 2>/dev/null |
        awk '
        /^Package:/ {
            sub(/^Package:[[:space:]]*/, "")
            print
        }'
    done
done |
sort -u > all_active.txt


## create master list
cat all_software.txt \
    all_data-experiment.txt \
    all_data-annotation.txt \
    all_workflows.txt \
    all_books.txt |
sort -u > all_packages.txt

## get deprecated list 
comm -23 all_packages.txt <(sort -u all_active.txt) > all_deprecated.txt

## unset GITHUB_TOKEN
## unset GH_TOKEN
## gh auth logout
## gh auth login 



## loop over to add deprecation topic and archive 
set -u

SAFE_SLEEP=1.2

safe_sleep() {
    sleep "$SAFE_SLEEP"
}

BASE="/home/lkern/BioconductorPackages/Syncing"
MANIFEST="/home/lkern/BioconductorPackages/PkgManagement/manifest"

FAILURE_LOG="$BASE/deprecated_archive_failures.txt"
: > "$FAILURE_LOG"

record_failure() {
    echo "$1" | tee -a "$FAILURE_LOG"
}

echo "========================================"
echo "Bioconductor Deprecated Repository Processing"
echo "========================================"
echo "Input:  $MANIFEST/all_deprecated.txt"
echo "Log:    $FAILURE_LOG"
echo "Sleep:  ${SAFE_SLEEP}s"
echo "========================================"

while IFS= read -r pkg; do

    [[ -z "$pkg" ]] && continue

    echo
    echo "========================================"
    echo "Processing: $pkg"
    echo "========================================"

    safe_sleep

    if ! gh repo view "bioconductor-source/$pkg" >/dev/null 2>&1; then
        record_failure "$pkg: GitHub repository not found"
        continue
    fi

    echo "$pkg: adding topic bioc-deprecated"

    safe_sleep

    if ! gh repo edit "bioconductor-source/$pkg" \
        --add-topic "bioc-deprecated"; then

        record_failure "$pkg: topic add failed (bioc-deprecated)"
        continue
    fi

    echo "$pkg: topic added successfully"

    echo "$pkg: archiving repository"

    safe_sleep

    if ! gh repo archive "bioconductor-source/$pkg" --confirm; then

        record_failure "$pkg: archive failed"
        continue
    fi

    echo "$pkg: archived successfully"

done < "$MANIFEST/all_deprecated.txt"

echo
echo "========================================"
echo "Processing complete"
echo "========================================"

if [ -s "$FAILURE_LOG" ]; then
    echo "Failures were recorded in:"
    echo "$FAILURE_LOG"
else
    echo "No failures detected."
fi




## test on single package 
pkg="PACKAGE_NAME_HERE"
gh repo view "bioconductor-source/$pkg" \
    --json name,isArchived,url \
    --jq '"Name: \(.name)\nArchived: \(.isArchived)\nURL: \(.url)"'
gh repo edit "bioconductor-source/$pkg" --add-topic "bioc-deprecated"
gh repo archive "bioconductor-source/$pkg" --confirm
gh repo view "bioconductor-source/$pkg" \
    --json name,isArchived,url \
    --jq '"Name: \(.name)\nArchived: \(.isArchived)\nURL: \(.url)"'
