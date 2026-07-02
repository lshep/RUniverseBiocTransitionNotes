.MAX_TRIES <- 2

.ruPath <- function(pkg, branch, subpath = "") {
    if (subpath != "")
        subpath <- paste0(subpath, "/")
    paste0("https://", getUni(branch), ".r-universe.dev/", subpath, pkg)
}

.getFile <- function(file_url, save_path, max_retries = .MAX_TRIES,
                     quiet = TRUE) {
    for (i in 1:max_retries) {
        curl::curl_download(file_url, save_path, quiet = quiet)
        
        tryCatch({
            curl::curl_download(file_url, save_path, quiet = quiet)
            return(save_path)
        }, error = function(e) {
            message("Failed attempt ", i, " to download ", file_url)
            Sys.sleep(30)
        })
    }
    message("Failed to download ", file_url)
}

#' @examples
#' pkg_url <- .ruPath("BiocCheck", getUni("devel"))
#' getCitation(pkg_url)
#' 
#' @export
getCitation <- function(pkg_url, save_path, ext = "html") {
    if (is.null(save_path))
        save_path <- paste("citations", pkg, "citation.html", sep = "/")
    .getFile(paste(pkg_url, paste0("citation.", ext), sep = "/"),
             save_path)
}

#' @examples
#' pkg_url <- .ruPath("BiocCheck", getUni("devel"))
#' getLicense(pkg_url)
#' 
#' @export
getLicense <- function(pkg_url, save_path) {
    if (is.null(save_path))
        save_path <- paste("licenses", pkg, "LICENSE", sep = "/")
    .getFile(paste0(pkg_url, "LICENSE"), save_path)
}

#' manuals/pkg/refman/pkg.html
#' manuals/animalcules/man/animalcules.pdf
#' web/packages/pkg/refman/pkg.html
#' web/packages/pkg/pkg.pdf
#' @examples
#' pkg_url <- .ruPath("BiocCheck", getUni("devel"))
#' getManual(pkg, pkg_url, ext = "pdf")
#' 
#' @export
getManual <- function(pkg, pkg_url, save_path, ext = c("pdf", "html")) {
    stem <- paste0(pkg, ".", ext)
    if (is.null(save_path) && ext == "pdf")
        save_path <- paste("manuals", pkg, "refman", stem, sep = "/")
    else if (is.null(save_path) && ext == "html")
        save_path <- paste("manuals", pkg, "man", stem, sep = "/")
    suffix <-ifelse(ext == "pdf", paste0(pkg, ".pdf"), "doc/manual.html")
    .getFile(paste0(pkg_url, suffix), save_path)
}


#' @examples
#' pkg_url <- .ruPath("BiocCheck", getUni("devel"))
#' getNews(pkg_url)
#' 
#' @export
getNews <- function(pkg_url, save_path) {
    if (is.null(save_path))
        save_path <- paste("news", pkg, "NEWS", sep = "/")
    .getFile(paste0(pkg_url, "NEWS"), save_path)
}

#' @examples
#' pkg_url <- .ruPath("BiocCheck", getUni("devel"))
#' getReadme(pkg_url)
#' 
#' @export
getReadme <- function(pkg_url, save_url) {
    if (is.null(save_path))
        save_path <- paste("readme", pkg, "readme.html", sep = "/")
    .getFile(paste0(pkg_url, "doc/readme.html"), save_path)
}

#' @examples
#' pkg_url <- .ruPath("BiocCheck", getUni("devel"))
#' df <- getRuDf("BiocCheck", "devel")
#' view <- prepareView(df) 
#' vignettes <- view$vignettes
#'
#' @export
getVignettes <- function(vignettes, pkg_url, save_path) {
    if (is.null(save_path))
        save_path <- paste("vignettes", pkg, "inst/doc", sep = "/")
    for(vignette in vignettes) {
        .getFile(paste0(pkg_url, vignette),
                 paste(save_path, vignette, sep = "/"))
    }
}

#' @export
getArtifacts <- function(pkg, branch, view) {
    uni <- getUni(branch)
    pkg_url <- .ruPath(pkg, uni)
    getCitation(pkg_url)
    getLicense(pkg_url)
    getManual(pkg, pkg_url, "pdf")
    getManual(pkg, pkg_url, "html")
    getNews(pkg_url)
    getReadme(pkg_url)
    getVignettes(view$assets, pkg_url)
}