import os
import csv
import requests
from datetime import datetime, timedelta
import subprocess
import re
import sys
import yaml
import textwrap

# ------------------------------
# Parse R-Universe Package API
#   For Build Results from SPB 
# ------------------------------
#ef parse_runiverse_build(pkg):

pkg = "Biostrings"
branch = "release"

def major_minor_version(v):
    if not v:
        return None
    return ".".join(str(v).strip().split(".")[:2])

def wrap_dcf(x, width=78, indent=8):
    if not x:
        return None
    return "\n".join(
        textwrap.wrap(
            x,
            width=width,
            subsequent_indent=" " * indent
        )
    )

def fmt_deps(role):
    rows = [x for x in deps if x.get("role") == role]
    if not rows:
        return None
    vals = []
    for x in rows:
        pkg = x.get("package")
        version = x.get("version")
        if version is None:
            vals.append(pkg)
        else:
            vals.append(f"{pkg} ({version})")
    return ", ".join(vals)

# -----------------------------
# Platform policy
# -----------------------------
platforms_ok = ["source"]
platforms_warnings = ["bioc-check", "linux", "macos", "windows"]
ALWAYS_KEEP = ["source", "bioc-check"]

build_clean = True
bioc_r_version = None
RUNIVERSE = None
full_version = None

try:
    cfg_url = "https://bioconductor.org/config.yaml"
    cfg_resp = requests.get(cfg_url, timeout=30)
    cfg_resp.raise_for_status()
    config = yaml.safe_load(cfg_resp.text)
    if branch == "release":
        full_version = config.get("r_version_associated_with_release","")
        RUNIVERSE = "bioc-release"
    else:
        full_version = config.get("r_version_associated_with_devel","")
        RUNIVERSE = "bioc"
    bioc_r_version = major_minor_version(full_version)
    print(f"[DEBUG] Bioconductor universe: {RUNIVERSE}")
    print(f"[DEBUG] Bioconductor R version: {bioc_r_version}")
except Exception as e:
    print(f"[WARN] Could not fetch Bioconductor config, skipping R filtering: {e}")

url = f"https://{RUNIVERSE}.r-universe.dev/api/packages/{pkg}"

try:
    resp = requests.get(url, timeout=10)
    if resp.status_code == 404:
        print(f"❌ Package `{pkg}` not available in R-universe (likely build failure)")
        #return {}
    resp.raise_for_status()
    data = resp.json()
except requests.RequestException as e:
    print(f"⚠️ Could not fetch R-universe data for `{pkg}`")
    #return {}


build_url = data.get("_buildurl")

# -----------------------------
# HARD FAILURE CASE 
# -----------------------------
failure_msg = data.get("_failure")
if failure_msg:
    fail_build_url = failure_msg.get("buildurl") or build_url
    print(f"🚨 R-universe build failed for `{pkg}` ")
    #return {}

jobs = data.get("_jobs", [])


Depends = fmt_deps("Depends")
Imports = fmt_deps("Imports")
Suggests = fmt_deps("Suggests")


date_pub = data.get("Date/Publication")
date_short = date_pub[:10] if date_pub else None

dcf = {
    "Package": data.get("Package"),
    "Version": data.get("Version"),
    "Depends": Depends,
    "Imports": Imports,
    "Suggests": Suggests,
    "License": data.get("License"),
    "MD5sum": data.get("MD5sum"),
    "NeedsCompilation": data.get("NeedsCompilation"),
    "Title": data.get("Title"),
    "Description": wrap_dcf(data.get("Description")),
    "biocViews": data.get("biocViews"),
    "Author": wrap_dcf(data.get("Author")),
    "Maintainer": data.get("Maintainer"),
    "URL": data.get("URL"),
    "VignetteBuilder": data.get("VignetteBuilder"),
    "BugReports": data.get("BugReports"),
    "git_url": data.get("_upstream"),
    "git_branch": "",
    "git_last_commit": data.get("RemoteSha"),
    "git_last_commit_date": date_short,
    "Date/Publication": date_short,
}


## I was testing with Biostrings and hte RemoteSha retrieved was not the same as
## the one when I navigated to the website version? 
## Is there a delay?? 




>>> data.get("_assets")
['extra/Biostrings.html', 'extra/citation.cff', 'extra/citation.html', 'extra/citation.json', 'extra/citation.txt', 'extra/contents.json', 'extra/NEWS.html', 'extra/NEWS.txt', 'extra/readme.html', 'extra/readme.md', 'manual.pdf']


>>> data.get("_vignettes")
[{'source': 'Biostrings2Classes.Rnw', 'filename': 'Biostrings2Classes.pdf', 'title': 'A short presentation of the basic classes defined in Biostrings 2', 'engine': 'utils::Sweave', 'headings': [], 'created': '2013-11-01 19:50:36', 'modified': '2013-11-01 19:50:36', 'commits': 1}, {'source': 'BiostringsQuickOverview.Rnw', 'filename': 'BiostringsQuickOverview.pdf', 'title': 'Biostrings Quick Overview', 'engine': 'utils::Sweave', 'headings': [], 'created': '2013-11-01 19:50:36', 'modified': '2024-04-23 05:10:42', 'commits': 6}, {'source': 'matchprobes.Rmd', 'filename': 'matchprobes.html', 'title': 'Using oligonucleotide microarray reporter sequence information for preprocessing and quality assessment', 'author': 'Wolfgang Huber, Robert Gentleman', 'engine': 'knitr::rmarkdown', 'headings': ['Overview', 'Using probe packages', 'Basic functions', 'Reverse and complementary sequence', 'Matching sets of probes against each other', 'Base content', 'Relating to the features of an AffyBatch', 'Some sequence related "preprocessing and quality" plots'], 'created': '2023-04-14 03:17:19', 'modified': '2024-02-12 17:48:02', 'commits': 2}, {'source': 'MultipleAlignments.Rmd', 'filename': 'MultipleAlignments.html', 'title': 'MultipleAlignment Objects', 'author': 'Marc Carlson, Beryl Kanali', 'engine': 'knitr::rmarkdown', 'headings': ['Introduction', 'Creation and masking', 'Analytic utilities', 'Exporting to file', 'Session Information'], 'created': '2024-06-07 17:02:07', 'modified': '2025-05-09 05:50:52', 'commits': 2}, {'source': 'PairwiseAlignments.Rnw', 'filename': 'PairwiseAlignments.pdf', 'title': 'Pairwise Sequence Alignments', 'engine': 'utils::Sweave', 'headings': [], 'created': '2013-11-01 19:50:36', 'modified': '2024-04-23 05:10:42', 'commits': 5}]


>>> data.get("_binaries")
[{'r': '4.7.0', 'os': 'linux', 'version': '2.80.1', 'date': '2026-05-22T18:49:53.000Z', 'distro': 'noble', 'arch': 'aarch64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '9c1805d903175a1951118512bb5b829922145e2f5d6a50bc30b4cdc745973574', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.7.0', 'os': 'linux', 'version': '2.80.1', 'date': '2026-05-22T18:50:48.000Z', 'distro': 'noble', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '6f7a9d3033dac0d797faf478c2548d7e3208fd70a725682268aca0f075b45923', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.6.0', 'os': 'linux', 'version': '2.80.1', 'date': '2026-05-22T18:50:24.000Z', 'distro': 'noble', 'arch': 'aarch64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '8de95b8eebb63a2b4912b1c6b5f0833412b2ae82dcade04c8853ffc14b85b971', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.6.0', 'os': 'linux', 'version': '2.80.1', 'date': '2026-05-22T18:51:05.000Z', 'distro': 'noble', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '79fbf91acb4b870cd5517b092614ee82f5f8cfd9aabe2569d68e7b105c8fbf60', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.5.3', 'os': 'mac', 'version': '2.80.1', 'date': '2026-05-22T19:13:38.000Z', 'arch': 'aarch64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '9e48bec523c7ffff717f0c5e1926ec3b3cdca6d814d20ef3e2c68de9a1d8bbea', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.5.3', 'os': 'mac', 'version': '2.80.1', 'date': '2026-05-22T18:51:03.000Z', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': 'b25d2b0c1552c8e24a34dbb6baadea3afe2c521bfdd4d1a3803c773388f42a94', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.6.0', 'os': 'mac', 'version': '2.80.1', 'date': '2026-05-22T19:16:34.000Z', 'arch': 'aarch64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '69f34860d96ffd24f5dd7834ac79e8ad133d915e7d752b05888ab5614def501a', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.6.0', 'os': 'mac', 'version': '2.80.1', 'date': '2026-05-22T18:51:55.000Z', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '7bdee17cf473c2c8cbde62c7b437a27a6082eb800fd5f4b6059b2e6acd5a5332', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.6.0', 'os': 'wasm', 'version': '2.80.1', 'date': '2026-05-22T18:50:10.000Z', 'arch': 'emscripten', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '6ea99aee6abbc27dac1cc2b140cf5e9a86210ea0d284db25c4b25e5cf8870c60', 'status': 'success', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.7.0', 'os': 'win', 'version': '2.80.1', 'date': '2026-05-22T18:48:17.000Z', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '502225792c9fdda7fb64a0fe820ba6ab27df9ee10d8b1e3d512adb90d861ca61', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.5.3', 'os': 'win', 'version': '2.80.1', 'date': '2026-05-22T18:48:10.000Z', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': 'bea063ed08cabf72910415c52176dc23e4fdf92538888f6dbb30c072b1a53757', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}, {'r': '4.6.0', 'os': 'win', 'version': '2.80.1', 'date': '2026-05-22T18:49:07.000Z', 'arch': 'x86_64', 'commit': 'bc262d5f452e0724e2f68696387d30e0b33e85b0', 'fileid': '800de377cb2d797ba1710fe462b7a3d7732112d69add31ae1db768cfbd009023', 'status': 'success', 'check': 'WARNING', 'buildurl': 'https://github.com/r-universe/bioc-release/actions/runs/26282417684'}]

















# -----------------------------
# HELPER FUNCTIONS
# -----------------------------
def matches_r_version(job_r):
    if not bioc_r_version:
        return True
    if not job_r:
        return False
    return str(job_r).startswith(str(bioc_r_version))

def keep_platform(platform, job_r):
    p = (platform or "").lower()
    # ALWAYS KEEP CORE
    if any(k in p for k in ALWAYS_KEEP):
        return True
    # R filtering applies only if config exists
    if bioc_r_version:
        return matches_r_version(job_r)
    return True

def match_platform(platform, key):
    return key in (platform or "").lower()

# -----------------------------
# FILTER JOBS
# -----------------------------
filtered = []

for job in jobs:
    if not isinstance(job, dict):
        continue
    platform = str(job.get("config"))
    job_r = job.get("r")
    if keep_platform(platform, job_r):
        filtered.append(job)

if not filtered:
    return {
        "status": ["UNKNOWN"],
        "message": f"⚠️ No filtered check results available for `{pkg}`",
        "_build_clean": False
    }

rows = []
unique_statuses = set()

for job in filtered:
    platform = str(job.get("config"))
    rver = job.get("r")
    status_str = str(job.get("check", "UNKNOWN")).upper()
    if status_str == "OK":
        status = "✅ OK"
    elif status_str == "NOTE":
        status = "ℹ️ NOTE"
    elif status_str == "WARNING":
        status = "⚠️ WARNING"
    elif status_str == "ERROR":
        status = "❌ ERROR"
    else:
        status = "❓ UNKNOWN"
    plat_lower = platform.lower()
    if any(match_platform(plat_lower, p) for p in platforms_ok):
        # strict
        if status_str not in ["OK", "NOTE"]:
            build_clean = False
            print(f"[FAIL] {pkg} {platform} expected OK/NOTE got {status_str}")
    elif any(match_platform(plat_lower, p) for p in platforms_warnings):
        # lenient
        if status_str not in ["OK", "NOTE", "WARNING"]:
            build_clean = False
            print(f"[FAIL] {pkg} {platform} expected OK/NOTE/WARNING got {status_str}")
    else:
        if status_str != "OK":
            build_clean = False
            print(f"[FAIL] {pkg} {platform} unexpected platform rule got {status_str}")
    if status == "❌ ERROR":
        unique_statuses.add("ERROR")
    elif status == "⚠️ WARNING":
        unique_statuses.add("WARNING")
    elif status == "ℹ️ NOTE":
        unique_statuses.add("NOTE")
    elif status == "❓ UNKNOWN":
        unique_statuses.add("UNKNOWN")
    else:
        unique_statuses.add("OK")
    job_url = f"{build_url}/job/{job.get('job') or job.get('artifact')}" if build_url else None
    link = f"[run]({job_url})" if job_url else ""
    rows.append({
        "platform": platform,
        "r": rver,
        "status": status,
        "job_id": job.get("job") or job.get("artifact"),
        "link": link
    })

# -----------------------------
# BUILD RESULT FILTERED TABLE 
# -----------------------------
header = "| Platform | R | Status | URL |\n|----------|---|--------|------|\n"

def platform_priority(p):
    p = (p or "").lower()
    if "source" in p:
         return 0
    if "bioc-check" in p or "bioccheck" in p:
        return 1
    return 2

lines = []
for r in sorted(rows, key=lambda x: (platform_priority(x["platform"]), x["platform"], str(x["r"]))):
    lines.append(
        f"| {r['platform']} | {r['r']} | {r['status']} | {r['link']} |"
    )

table = header + "\n".join(lines)

return {
    "status": sorted(unique_statuses),
    "message": f"📊 R-universe check results for `{pkg}`\n\n{table}",
    "_build_clean": build_clean
}




# Package: Biostrings
# Version: 2.80.0
# Depends: R (>= 4.1.0), BiocGenerics (>= 0.37.0), S4Vectors (>=
#         0.27.12), IRanges (>= 2.31.2), XVector (>= 0.37.1), Seqinfo
# Imports: methods, utils, grDevices, stats, crayon
# LinkingTo: S4Vectors, IRanges, XVector
# Suggests: graphics, pwalign, BSgenome (>= 1.13.14),
#         BSgenome.Celegans.UCSC.ce2 (>= 1.3.11),
#         BSgenome.Dmelanogaster.UCSC.dm3 (>= 1.3.11),
#         BSgenome.Hsapiens.UCSC.hg18, drosophila2probe, hgu95av2probe,
#         hgu133aprobe, GenomicFeatures (>= 1.3.14), hgu95av2cdf, affy
#         (>= 1.41.3), affydata (>= 1.11.5), RUnit, BiocStyle, knitr,
#         testthat (>= 3.0.0), covr
# License: Artistic-2.0
# Archs: x64
# MD5sum: ab502c6da1311ed684910f8cce8d3ef8
# NeedsCompilation: yes
# Title: Efficient manipulation of biological strings
# Description: Memory efficient string containers, string matching
#         algorithms, and other utilities, for fast manipulation of large
#         biological sequences or sets of sequences.
# biocViews: SequenceMatching, Alignment, Sequencing, Genetics,
#         DataImport, DataRepresentation, Infrastructure
# Author: HervÃ© PagÃ¨s [aut, cre], Patrick Aboyoun [aut], Robert Gentleman
#         [aut], Saikat DebRoy [aut], Vince Carey [ctb], Nicolas Delhomme
#         [ctb], Felix Ernst [ctb], Wolfgang Huber [ctb] ('matchprobes'
#         vignette), Beryl Kanali [ctb] (Converted 'MultipleAlignments'
#         vignette from Sweave to RMarkdown), Haleema Khan [ctb]
#         (Converted 'matchprobes' vignette from Sweave to RMarkdown),
#         Aidan Lakshman [ctb], Kieran O'Neill [ctb], Valerie Obenchain
#         [ctb], Marcel Ramos [ctb], Albert Vill [ctb], Jen Wokaty [ctb]
#         (Converted 'matchprobes' vignette from Sweave to RMarkdown),
#         Erik Wright [ctb]
# Maintainer: HervÃ© PagÃ¨s <hpages.on.github@gmail.com>
# URL: https://bioconductor.org/packages/Biostrings
# VignetteBuilder: knitr
# BugReports: https://github.com/Bioconductor/Biostrings/issues
# git_url: https://git.bioconductor.org/packages/Biostrings
# git_branch: RELEASE_3_23
# git_last_commit: 8e49c26
# git_last_commit_date: 2026-04-28
# Date/Publication: 2026-04-28
# source.ver: src/contrib/Biostrings_2.80.0.tar.gz
# win.binary.ver: bin/windows/contrib/4.6/Biostrings_2.80.0.zip
# mac.binary.big-sur-x86_64.ver:
#         bin/macosx/big-sur-x86_64/contrib/4.6/Biostrings_2.80.0.tgz
# mac.binary.sonoma-arm64.ver:
#         bin/macosx/sonoma-arm64/contrib/4.6/Biostrings_2.80.0.tgz
# vignettes: vignettes/Biostrings/inst/doc/Biostrings2Classes.pdf,
#         vignettes/Biostrings/inst/doc/BiostringsQuickOverview.pdf,
#         vignettes/Biostrings/inst/doc/PairwiseAlignments.pdf,
#         vignettes/Biostrings/inst/doc/matchprobes.html,
#         vignettes/Biostrings/inst/doc/MultipleAlignments.html
# vignetteTitles: A short presentation of the basic classes defined in
#         Biostrings 2, Biostrings Quick Overview, Pairwise Sequence
#         Alignments, Handling probe sequence information, Multiple
#         Alignments
# hasREADME: FALSE
# hasNEWS: TRUE
# hasINSTALL: FALSE
# hasLICENSE: FALSE
# Rfiles: vignettes/Biostrings/inst/doc/Biostrings2Classes.R,
#         vignettes/Biostrings/inst/doc/matchprobes.R,
#         vignettes/Biostrings/inst/doc/MultipleAlignments.R
# dependsOnMe: alabaster.string, altcdfenvs, amplican, Basic4Cseq, BRAIN,
#         BSgenome, BSgenomeForge, chimeraviz, ChIPanalyser, ChIPsim,
#         cigarillo, cleaver, CODEX, CRISPRseek, DECIPHER, deepSNV,
#         GeneRegionScan, GenomicAlignments, GOTHiC, HelloRanges,
#         igblastr, kebabs, MethTargetedNGS, minfi, Modstrings, MotifDb,
#         motifTestR, msa, muscle, oligo, ORFhunteR, periodicDNA,
#         pqsfinder, pwalign, PWMEnrich, QSutils, queeems,
#         R453Plus1Toolbox, R4RNA, rBLAST, REDseq, Rsamtools, RSVSim,
#         rSWeeP, sangeranalyseR, sangerseqR, SCAN.UPC, SELEX, ShortRead,
#         SICtools, SimFFPE, ssviz, Structstrings, svaNUMT, systemPipeR,
#         topdownr, transmogR, TreeSummarizedExperiment, triplex, VarCon,
#         FDb.FANTOM4.promoters.hg19, pd.ag, pd.aragene.1.0.st,
#         pd.aragene.1.1.st, pd.ath1.121501, pd.barley1,
#         pd.bovgene.1.0.st, pd.bovgene.1.1.st, pd.bovine, pd.bsubtilis,
#         pd.cangene.1.0.st, pd.cangene.1.1.st, pd.canine, pd.canine.2,
#         pd.celegans, pd.chicken, pd.chigene.1.0.st, pd.chigene.1.1.st,
#         pd.chogene.2.0.st, pd.chogene.2.1.st, pd.citrus,
#         pd.clariom.d.human, pd.clariom.s.human, pd.clariom.s.human.ht,
#         pd.clariom.s.mouse, pd.clariom.s.mouse.ht, pd.clariom.s.rat,
#         pd.clariom.s.rat.ht, pd.cotton, pd.cyngene.1.0.st,
#         pd.cyngene.1.1.st, pd.cyrgene.1.0.st, pd.cyrgene.1.1.st,
#         pd.cytogenetics.array, pd.drogene.1.0.st, pd.drogene.1.1.st,
#         pd.drosgenome1, pd.drosophila.2, pd.e.coli.2, pd.ecoli,
#         pd.ecoli.asv2, pd.elegene.1.0.st, pd.elegene.1.1.st,
#         pd.equgene.1.0.st, pd.equgene.1.1.st, pd.felgene.1.0.st,
#         pd.felgene.1.1.st, pd.fingene.1.0.st, pd.fingene.1.1.st,
#         pd.genomewidesnp.5, pd.genomewidesnp.6, pd.guigene.1.0.st,
#         pd.guigene.1.1.st, pd.hc.g110, pd.hg.focus, pd.hg.u133.plus.2,
#         pd.hg.u133a, pd.hg.u133a.2, pd.hg.u133a.tag, pd.hg.u133b,
#         pd.hg.u219, pd.hg.u95a, pd.hg.u95av2, pd.hg.u95b, pd.hg.u95c,
#         pd.hg.u95d, pd.hg.u95e, pd.hg18.60mer.expr,
#         pd.ht.hg.u133.plus.pm, pd.ht.hg.u133a, pd.ht.mg.430a,
#         pd.hta.2.0, pd.hu6800, pd.huex.1.0.st.v2, pd.hugene.1.0.st.v1,
#         pd.hugene.1.1.st.v1, pd.hugene.2.0.st, pd.hugene.2.1.st,
#         pd.maize, pd.mapping250k.nsp, pd.mapping250k.sty,
#         pd.mapping50k.hind240, pd.mapping50k.xba240, pd.margene.1.0.st,
#         pd.margene.1.1.st, pd.medgene.1.0.st, pd.medgene.1.1.st,
#         pd.medicago, pd.mg.u74a, pd.mg.u74av2, pd.mg.u74b,
#         pd.mg.u74bv2, pd.mg.u74c, pd.mg.u74cv2, pd.mirna.1.0,
#         pd.mirna.2.0, pd.mirna.3.0, pd.mirna.4.0, pd.moe430a,
#         pd.moe430b, pd.moex.1.0.st.v1, pd.mogene.1.0.st.v1,
#         pd.mogene.1.1.st.v1, pd.mogene.2.0.st, pd.mogene.2.1.st,
#         pd.mouse430.2, pd.mouse430a.2, pd.mta.1.0, pd.mu11ksuba,
#         pd.mu11ksubb, pd.nugo.hs1a520180, pd.nugo.mm1a520177,
#         pd.ovigene.1.0.st, pd.ovigene.1.1.st, pd.pae.g1a,
#         pd.plasmodium.anopheles, pd.poplar, pd.porcine,
#         pd.porgene.1.0.st, pd.porgene.1.1.st, pd.rabgene.1.0.st,
#         pd.rabgene.1.1.st, pd.rae230a, pd.rae230b, pd.raex.1.0.st.v1,
#         pd.ragene.1.0.st.v1, pd.ragene.1.1.st.v1, pd.ragene.2.0.st,
#         pd.ragene.2.1.st, pd.rat230.2, pd.rcngene.1.0.st,
#         pd.rcngene.1.1.st, pd.rg.u34a, pd.rg.u34b, pd.rg.u34c,
#         pd.rhegene.1.0.st, pd.rhegene.1.1.st, pd.rhesus, pd.rice,
#         pd.rjpgene.1.0.st, pd.rjpgene.1.1.st, pd.rn.u34, pd.rta.1.0,
#         pd.rusgene.1.0.st, pd.rusgene.1.1.st, pd.s.aureus, pd.soybean,
#         pd.soygene.1.0.st, pd.soygene.1.1.st, pd.sugar.cane, pd.tomato,
#         pd.u133.x3p, pd.vitis.vinifera, pd.wheat, pd.x.laevis.2,
#         pd.x.tropicalis, pd.xenopus.laevis, pd.yeast.2, pd.yg.s98,
#         pd.zebgene.1.0.st, pd.zebgene.1.1.st, pd.zebrafish, harbChIP,
#         JASPAR2014, NestLink, generegulation, sequencing,
#         CleanBSequences, SubVis
# importsMe: AllelicImbalance, AnnotationHubData, appreci8R, AssessORF,
#         ATACseqQC, BBCAnalyzer, BCRANK, bcSeq, BEAT, betterChromVAR,
#         BgeeCall, biovizBase, branchpointer, bsseq, BUMHMM, BUSpaRse,
#         CAGEr, CellBarcode, ChIPpeakAnno, ChIPseqR, ChIPsim, chromVAR,
#         circRNAprofiler, CircSeqAlignTk, cleanUpdTSeq, CleanUpRNAseq,
#         cliProfiler, ClustIRR, CNEr, CNVfilteR, cogeqc, compEpiTools,
#         coRdon, crisprBase, crisprBowtie, crisprDesign, crisprScore,
#         crisprShiny, CrispRVariants, crisprViz, customProDB, dada2,
#         dagLogo, DAMEfinder, Damsel, decompTumor2Sig, diffHic,
#         DMRcaller, DNAshapeR, DominoEffect, DOTSeq, doubletrouble,
#         DspikeIn, DuplexDiscovereR, easyRNASeq, EDASeq,
#         enhancerHomologSearch, ensembldb, epiSeeker, EpiTxDb, esATAC,
#         eudysbiome, EventPointer, factR, FastqCleaner, FLAMES,
#         fRagmentomics, fraq, G4SNVHunter, GA4GHclient, gcapc, gcrma,
#         gDNAx, GeneRegionScan, genomation, GenomAutomorphism,
#         GenomicAlignments, GenomicDistributions, GenomicFeatures,
#         GenomicScores, GenVisR, geomeTriD, ggbio, ggmsa, gmapR, gmoviz,
#         GRaNIE, GUIDEseq, Gviz, gwascat, h5vc, heatmaps, HiCaptuRe,
#         HiCPotts, HiLDA, HiTC, icetea, idpr, immReferent, IntEREst,
#         IONiseR, ipdDb, IsoformSwitchAnalyzeR, KEGGREST, LACHESIS,
#         LymphoSeq, m6Aboost, MatrixRider, MDTS, MEDIPS, MEDME, memes,
#         MesKit, metabinR, metaseqR2, methimpute, methodical,
#         methylPipe, methylscaper, mia, microbiome, MicrobiotaProcess,
#         microRNA, MMDiff2, mobileRNA, monaLisa, Motif2Site,
#         motifcounter, motifmatchr, MotifPeeker, motifStack, MSA2dist,
#         MSnID, MSstatsLiP, MSstatsPTM, multicrispr, MungeSumstats,
#         musicatk, MutationalPatterns, MutSeqR, NanoMethViz,
#         NanoStringNCTools, ngsReports, nucleR, oligoClasses, OmaDB,
#         openPrimeR, ORFik, OTUbase, packFinder, pdInfoBuilder,
#         PhyloProfile, phyloseq, PICB, pipeFrame, planttfhunter, podkat,
#         posDemux, postNet, primirTSS, proBAMr, procoil, ProteoDisco,
#         PureCN, Pviz, qPLEXanalyzer, qsea, QuasR, r3Cseq, raer, ramwas,
#         RCAS, Rcpi, recoup, regioneR, regutools, REMP, RESOLVE, rfaRm,
#         rhinotypeR, RiboCrypt, ribosomeProfilingQC, RNAmodR, rprimer,
#         Rqc, rtracklayer, sarks, scanMiR, scanMiRApp, scifer, scmeth,
#         SCOPE, scoreInvHap, scoup, scPipe, scruff, SEMPLR, SeqArray,
#         seqPattern, SGSeq, signeR, SigsPack,
#         SingleMoleculeFootprinting, sitadela, SNPhood,
#         SomaticSignatures, SparseSignatures, spiky, SpliceImpactR,
#         SpliceWiz, SPLINTER, sscu, StructuralVariantAnnotation,
#         supersigs, surfaltr, svaRetro, SynExtend, SynMut, syntenet,
#         TAPseq, TENET, TFBSTools, transite, tRNA, tRNAdbImport,
#         tRNAscanImport, TVTB, txcutr, tximeta, UMI4Cats,
#         universalmotif, VariantAnnotation, VariantExperiment,
#         VariantFiltering, VariantTools, wavClusteR, YAPSA, EuPathDB,
#         FDb.InfiniumMethylation.hg18, FDb.InfiniumMethylation.hg19,
#         pd.081229.hg18.promoter.medip.hx1,
#         pd.2006.07.18.hg18.refseq.promoter,
#         pd.2006.07.18.mm8.refseq.promoter,
#         pd.2006.10.31.rn34.refseq.promoter, pd.charm.hg18.example,
#         pd.feinberg.hg18.me.hx1, pd.feinberg.mm8.me.hx1, pd.mirna.3.1,
#         MetaScope, microbiomeDataSets, pd.atdschip.tiling,
#         PhyloProfileData, systemPipeRdata, seqpac, AbSolution,
#         ActiveDriverWGS, alakazam, AntibodyForests, BASiNET,
#         BASiNETEntropy, BIGr, biomartr, copyseparator, crispRdesignR,
#         CSESA, cubar, DNAmotif, eDNAfuns, ensembleTax, EpiSemble,
#         GB5mcPred, genBaRcode, GencoDymo2, GenomicSig, iimi, kmeRtone,
#         longreadvqs, metaCluster, MitoHEAR, OpEnCAST, OpEnHiMR, PACVr,
#         piglet, QsRutils, refseqR, revert, seqmagick, SQMtools,
#         SVAlignR, tidyGenR, TmCalculator, vhcub, VIProDesign
# suggestsMe: alabaster.files, annotate, AnnotationForge, AnnotationHub,
#         autonomics, bambu, BANDITS, CSAR, DNAcycP2, eisaR,
#         GenomicFiles, GenomicRanges, GenomicTuples, ggseqalign, ggtree,
#         GWASTools, HiContacts, HPiP, maftools, methrix, methylumi,
#         MiRaGE, mitoClone2, mutscan, nuCpos, plyinteractions, PTMods,
#         RNAmodR.AlkAnilineSeq, rpx, rTRM, screenCounter, splatter,
#         systemPipeTools, treeio, tripr, XVector,
#         SNPlocs.Hsapiens.dbSNP144.GRCh37,
#         SNPlocs.Hsapiens.dbSNP144.GRCh38,
#         SNPlocs.Hsapiens.dbSNP149.GRCh38,
#         SNPlocs.Hsapiens.dbSNP150.GRCh38,
#         SNPlocs.Hsapiens.dbSNP155.GRCh37,
#         SNPlocs.Hsapiens.dbSNP155.GRCh38,
#         XtraSNPlocs.Hsapiens.dbSNP144.GRCh37,
#         XtraSNPlocs.Hsapiens.dbSNP144.GRCh38, BeadArrayUseCases, baseq,
#         bbl, bio3d, BOLDconnectR, demulticoder, file2meco, geneviewer,
#         gkmSVM, gwas2crispr, inDAGO, karyotapR, maGUI, msaR,
#         NameNeedle, orthGS, phangorn, polyRAD, protr, sigminer, Signac,
#         tidysq
# linksToMe: DECIPHER, kebabs, MatrixRider, posDemux, pwalign, Rsamtools,
#         ShortRead, triplex, VariantAnnotation, VariantFiltering
# dependencyCount: 14








