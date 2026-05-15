


# repos=(
#   pkgA
#   pkgB
#   pkgC
# )

# for repo in "${repos[@]}"; do
#   echo "Syncing $repo"

#   cd "$repo" || continue

#   git fetch upstream

#   git push github \
#     upstream/devel:devel \
#     upstream/RELEASE_3_23:RELEASE_3_23

#   cd ..
# done

cd /home/lkern/BioconductorPackages/PkgManagement/manifest
for branch in devel RELEASE_3_23
do
    for file in software.txt data-experiment.txt data-annotation.txt workflows.txt
    do
        git show "${branch}:${file}" 2>/dev/null
    done
done |
grep '^Package:' |
sed 's/^Package:[[:space:]]*//' |
sort -u > /home/lkern/BioconductorPackages/PkgManagement/current_packages.txt



# sed 1d /home/lkern/BioconductorPackages/PkgManagement/current_packages.txt | 
# sed 's/Package: //g' | sed '/^\s*$/d' | while read pkg; do
#     if [ ! -d "/home/lkern/BioconductorPackages/Syncing/$pkg" ]; then
# 	echo $pkg
# 	cd /home/lkern/BioconductorPackages/Syncing/
# 	git clone git@git.bioconductor.org:packages/$pkg.git   
# 	cd /home/lkern/BioconductorPackages/Syncing/$pkg
# 	git remote add github git@github.com:bioconductor-source/$pkg.git   
#     else
# 	echo $pkg
# 	cd /home/lkern/BioconductorPackages/Syncing/$pkg
#     fi
#     git fetch origin
#     git push github \
#         origin/devel:devel \
#         origin/RELEASE_3_23:RELEASE_3_23	
# done

sed 1d /home/lkern/BioconductorPackages/PkgManagement/current_packages.txt |
sed 's/Package: //g' |
sed '/^\s*$/d' |
while read pkg; do
    echo "$pkg"
    if [ ! -d "/home/lkern/BioconductorPackages/Syncing/$pkg" ]; then
        cd /home/lkern/BioconductorPackages/Syncing/ || exit
        git clone git@git.bioconductor.org:packages/$pkg.git
        cd "/home/lkern/BioconductorPackages/Syncing/$pkg" || continue
        git remote add github git@github.com:bioconductor-source/$pkg.git
    else
        cd "/home/lkern/BioconductorPackages/Syncing/$pkg" || continue
    fi
    git fetch origin
    if git show-ref --verify --quiet refs/remotes/origin/devel; then
        git push github origin/devel:devel
    else
        echo "Missing devel branch for $pkg"
    fi
    if git show-ref --verify --quiet refs/remotes/origin/RELEASE_3_23; then
        git push github origin/RELEASE_3_23:RELEASE_3_23
    else
        echo "Missing RELEASE_3_23 branch for $pkg"
    fi
done
