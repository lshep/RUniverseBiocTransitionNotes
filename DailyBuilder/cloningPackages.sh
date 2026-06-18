## Clones all branches, tags, refs

# git clone --mirror <old-repo-url>
# cd repo.git
# git remote set-url origin <github-url>
# git push --mirror


## pushes literally all refs and also deletes refs on the destination that do not exist locally

## Be careful of the four that were moved over!! make sure git.bioconductor is
## updated for ontoProc, AnVIL, BiocCheck before we do this!!  




#
# Option 1: all ... see option 2 to add topics automatically during this step
#
#

cd /home/lkern/BioconductorPackages/PkgManagement/manifest
git for-each-ref --format='%(refname:short)' refs/heads/ | while read branch
do
    for file in software.txt data-experiment.txt data-annotation.txt workflows.txt
    do
        git show "${branch}:${file}" 2>/dev/null
    done
done |
grep '^Package:' |
sed 's/^Package:[[:space:]]*//' |
sort -u > /home/lkern/BioconductorPackages/PkgManagement/all_packages.txt


sed 1d /home/lkern/BioconductorPackages/PkgManagement/all_packages.txt |
sed 's/Package: //g' |
sed '/^\s*$/d' |
while read pkg; do
    echo "$pkg"
    if [ ! -d "/home/lkern/BioconductorPackages/Syncing/$pkg.git" ]; then
        cd /home/lkern/BioconductorPackages/Syncing/ || exit
        git clone --mirror git@git.bioconductor.org:packages/$pkg.git
        cd "/home/lkern/BioconductorPackages/Syncing/$pkg.git" || continue
        if ! gh repo view "bioconductor-source/$pkg" >/dev/null 2>&1; then
            gh repo create "bioconductor-source/$pkg" --public
        fi
        git remote set-url origin git@github.com:bioconductor-source/$pkg.git
        git push --mirror
	cd /home/lkern/BioconductorPackages/Syncing/ || exit
	rm -rf "$pkg.git"
    else
        echo "ERROR $pkg already exists"
    fi
done



#
#  Option 2: probably preferred
# 
#

### Or Keep per package type and include adding a topic

set -e
BASE="/home/lkern/BioconductorPackages/PkgManagement/manifest"
files=("software.txt" "data-experiment.txt" "data-annotation.txt" "workflows.txt")
declare -A OUTFILES=(
  ["software.txt"]="all_software.txt"
  ["data-experiment.txt"]="all_data-experiment.txt"
  ["data-annotation.txt"]="all_data-annotation.txt"
  ["workflows.txt"]="all_workflows.txt"
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
files=("all_software.txt" "all_data-experiment.txt" "all_data-annotation.txt" "all_workflows.txt")
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


## loop over mirroring and creating topic 
## MUST set up gh auth to someone with admin/create access
##    first to crete repos that have not been initilized yet
##


files=(
  "all_software.txt:software"
  "all_data-experiment.txt:data-experiment"
  "all_data-annotation.txt:data-annotation"
  "all_workflows.txt:workflow"
)

BASE="/home/lkern/BioconductorPackages/Syncing"

FAILURE_LOG="$BASE/failures_detected.txt"
: > "$FAILURE_LOG"

record_failure () {
    echo "$1" | tee -a "$FAILURE_LOG"
}

for entry in "${files[@]}"; do
    file="${entry%%:*}"
    topic="${entry##*:}"

    pushd "$BASE" >/dev/null || exit 1

    while read pkg; do

        if [ -d "$pkg.git" ]; then
            record_failure "$pkg: local repo already exists"
            continue
        fi

        if ! git clone --mirror "git@git.bioconductor.org:packages/$pkg.git"; then
            record_failure "$pkg: clone failed"
            continue
        fi

        if ! pushd "$pkg.git" >/dev/null; then
            record_failure "$pkg: cannot enter repo dir"
            rm -rf "$BASE/$pkg.git"
            continue
        fi

        if ! gh repo view "bioconductor-source/$pkg" >/dev/null 2>&1; then
            if ! gh repo create "bioconductor-source/$pkg" --public; then
                record_failure "$pkg: repo creation failed"
                popd >/dev/null
                rm -rf "$BASE/$pkg.git"
                continue
            fi
        fi

        git remote set-url origin "git@github.com:bioconductor-source/$pkg.git"

        if ! git push --mirror; then
            record_failure "$pkg: push failed"
            popd >/dev/null
            rm -rf "$BASE/$pkg.git"
            continue
        fi

        gh repo edit "bioconductor-source/$pkg" --add-topic "$topic" \
            || record_failure "$pkg: topic add failed ($topic)"

        gh repo edit "bioconductor-source/$pkg" --add-topic "bioc-r-package" \
            || record_failure "$pkg: topic add failed (bioc-r-package)"

        popd >/dev/null
        rm -rf "$BASE/$pkg.git"

    done < <(
        sed 1d "/home/lkern/BioconductorPackages/PkgManagement/manifest/$file" |
        sed 's/Package: //g' |
        sed '/^\s*$/d'
    )

    popd >/dev/null

done










####
# Test inner loop code
#!/usr/bin/env bash

#pkg="BiocMaintainerApp"
pkg="AnnotationHub"
ttopic="software"

BASE="/home/lkern/BioconductorPackages/Syncing"

echo "Testing package: $pkg"

cd "$BASE" || exit 1

# 1. Mirror clone (test only)
if [ ! -d "$pkg.git" ]; then
    echo "Cloning mirror..."
    git clone --mirror "git@git.bioconductor.org:packages/$pkg.git"
else
    echo "Local mirror already exists"
fi

cd "$pkg.git" || exit 1

# 2. Create GitHub repo if missing
echo "Checking GitHub repo..."
if ! gh repo view "bioconductor-source/$pkg" >/dev/null 2>&1; then
    echo "Creating GitHub repo..."
    gh repo create "bioconductor-source/$pkg" --public
else
    echo "GitHub repo already exists"
fi

# 3. Set remote
git remote set-url origin "git@github.com:bioconductor-source/$pkg.git"

# 4. Push mirror (⚠️ large operation)
echo "Pushing mirror..."
git push --mirror

# 5. Add topic
echo "Adding topic: $topic"
gh repo edit "bioconductor-source/$pkg" --add-topic "$topic"

echo "DONE"
