library(jsonlite)

url <- "https://bioc.r-universe.dev/api/packages/"
data <- fromJSON(url)


## We care about "_jobs" table
## however does not separate out R CMD build and R CMD check in reporting
## Can we get this information or is reporting overall status ok??


> data[20,"_jobs"]
[[1]]
           job time               config     r   check   artifact
1  62297269283  246          bioc-checks 4.5.2 WARNING 5352244547
2  62297269272  507   linux-devel-x86_64 4.6.0 WARNING 5352274862
3  62297269278  492 linux-release-x86_64 4.5.2 WARNING 5352273372
4  62297269260  405    macos-devel-arm64 4.6.0 WARNING 5352359183
5  62297269279  367  macos-release-arm64 4.5.2 WARNING 5352307297
6  62296829580  379               source 4.5.2   ERROR 5352211708
7  62297269265  194         wasm-release 4.5.1      OK 5352238226
8  62297269303  385        windows-devel 4.6.0 WARNING 5352261286
9  62297269308  396       windows-oldrel 4.4.3 WARNING 5352262717
10 62297269305  378      windows-release 4.5.2 WARNING 5352260482

> data[20,"_previous"]
[1] "1.17.2"

> data[20,1:6]
    Package Version       Date
20 svaRetro  1.17.3 2026-02-03
                                                           Title
20 Retrotransposed transcript detection from structural variants
                                                                      Author
20 Ruining Dong [aut, cre] (ORCID:\n<https://orcid.org/0000-0003-1433-0484>)
                         Maintainer
20 Ruining Dong <lnyidrn@gmail.com>


    
> data[20,"RemoteSha"]
[1] "02d27b461a8b3b0e6ec7fca1fd347508d9cbf5ef"



> data[20,"_commit"]
                                         id                           author
20 02d27b461a8b3b0e6ec7fca1fd347508d9cbf5ef Ruining Dong <lnyidrn@gmail.com>
                          committer
20 Ruining Dong <lnyidrn@gmail.com>
                                                                                                                                                                                                                                                                                                 message
20 Fix seqinfo compatibility for findOverlaps in newer Bioconductor\n\n- Sync complete seqinfo (seqlengths, genome, isCircular) from TxDb exons to\n  input GRanges for common chromosomes\n- This resolves MT chromosome length mismatch errors in R 4.6/Bioconductor 3.21+\n- Bump version to 1.17.3\n
         time
20 1770083840



> data[20,152:154]
   git_branch git_last_commit git_last_commit_date
20
<NA>            <NA>                 <NA>


> data[20,"StagedInstall"]
[1] NA

## What is the date of the last commit?? Is that somewhere??
## time 1770083840 what does this equate to?
## Is Date the date of the last run
## Difference of Date, Date/Publication, Packaged.Date
## Lots of NA in API??






##################################
##################################
##################################
##################################




library(jsonlite)

url <- "https://bioc.r-universe.dev/api/packages/BiocCheck"
data <- fromJSON(url)

##################################
##################################
##################################
##################################


## https://jwokaty.github.io/exploreBiocUniverse/

if (!require("universe", quietly = TRUE))
    install.packages("universe", repos = "https://ropensci.r-universe.dev")
library(universe)
options(max.print = 3000L)

ru_pkgs_i <- universe_all_packages("bioc", limit = 3000L)

                                        
## so would release be bioc-release??

ru_pkg_i[[21]]

do.call(rbind, lapply(temp$`_jobs`, as.data.frame))








library(tibble)

ru_status <- data.frame(Package = character(), Version = character(), 
                        Status = character(), Build = character(),
                        Check = character(), Comment = character())
                        #, Buildurl = character(),
                        # Commit = character())

for (i in seq_along(ru_pkgs_i)) {
#for (p in ru_pkgs_i) {
  p <- ru_pkgs_i[[i]]
  build <- c(status = NA, build = NA, check = NA, buildurl = NA)
  comment = ""
  for (j in seq_along(p[["_binaries"]])) {
  #for (b in p$`_binaries`) {
    b <- p[["_binaries"]][[j]]
    if (b$os == "linux" && b$r == "4.6.0") {
      build <- c(status = b$status, check = b$check, buildurl = b$buildurl)
      break
    }
  }
  if (is.na(build["status"])) {
    comment = "Missing R4.6 on Linux" 
  } else if (build["status"] == "success") {
    build["build"] <- "OK"
  } else if (build["status"] == "failure") {
    build["build"] <- "ERROR*"
    comment = build["buildurl"]
  } else if (build["status"] == "cancelled") {
    build["build"] <- "CANCELLED"
    comment = build["buildurl"]
  }
  ru_status <- ru_status |>
    add_row(Package = p$Package, Version = p$Version, Status = build["status"],
            Build = build["build"], Check = build["check"], Comment = comment)
            #, Buildurl = build["buildurl"], Commit = p$`_commit`$id)
}

# order by Package
ru_status <- ru_status[order(ru_status$Package), ]


## how in your script are you determine "Build" as it doesnt seem to line up?
## for example annotate is in R CMD check??

##
## How long before CRAN removed?? See adductomicsR where smoother removed 12-19
## It has a banner that the latest build failed but the results displayed and
## distributed are passing

##
## would it have propagated ERROR if it wasn't a rebuild? when does a rebuild
## take over the results table/artifacts?
## If it only keeps propagated how do you get results if it fails?
##     I see pulling package has a _failure entry so we have to check this too!
## But something like biocdbChebi has a page
## https://bioc.r-universe.dev/biodbChebi how does it have a source to
## distribute? is it because installation ok but failed on vignettes?
##  Does it have a page if it never Installs?

##
## Where I'm going ... when a build finishes dump a json with needed results to
## a bucket
## From that bucket create the parquet files 


## How does deprecating packages work if we sym release and devel branches -- we
## need to remove deprecated/removed packages manually if they were previously included??
