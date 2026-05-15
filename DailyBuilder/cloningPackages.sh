## Clones all branches, tags, refs

# git clone --mirror <old-repo-url>
# cd repo.git
# git remote set-url origin <github-url>
# git push --mirror


## pushes literally all refs and also deletes refs on the destination that do not exist locally

## Be careful of the four that were moved over!! make sure git.bioconductor is
## updated for ontoProc, AnVIL, BiocCheck before we do this!!  


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
    if [ ! -d "/home/lkern/BioconductorPackages/Syncing/$pkg" ]; then
        cd /home/lkern/BioconductorPackages/Syncing/ || exit
        git clone --mirror git@git.bioconductor.org:packages/$pkg.git
        cd "/home/lkern/BioconductorPackages/Syncing/$pkg" || continue
        git remote set-url origin github git@github.com:bioconductor-source/$pkg.git
        git push --mirror
    else
	echo "ERROR $pkg already exists"
    fi
done
 
