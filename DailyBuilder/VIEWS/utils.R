.PACKAGE_TYPES <- c("software", "data-annotation", "data-experiment",
                    "workflows", "books")

#getBiocVersion <- function(branch = c("devel", "release"),
#                           path = "https://bioconductor.org/config.yaml") {
#    config <- yaml::read_yaml(path)
#    ifelse(branch == "devel", config$devel_version, config$release_version)
#}

.save_as <- function(df, save_path, ext = c("json", "dcf")) {
  if (ex == "dcf") {
    write.dcf(df, save_path)
  } else {
    jsonlite::write_json(df, save_path)
  }
}

getUni <- function(branch) {
    ifelse(branch == "devel", "bioc", "bioc-release")
}

getRuDf <- function(pkg, branch) {
    uni <- getUni(branch)
    ru_api <- file.path(paste0("https://", uni, ".r-universe.dev/api/packages"),
                     pkg)
    jsonlite::fromJSON(ru_api)
}

.start_logger <- function(path, level = logger::INFO) {
  path <- file.path(tempdir(), tempfile(pattern = "log"))
  logger::log_threshold(level)
    logger::log_info("Logging on")
}

readManifest <- function(manifest_repo_url, branch) {
    path <- file.path(tempdir(), 
                      tempfile(pattern = "bioconductor-"),
                      "manifest")
    dir.create(path, recursive = TRUE)
    repo <- git2r::clone(manifest_repo_url, path, branch = branch)
    paths <- paste0(path, paste0(.PACKAGE_TYPES, ".txt"), sep = "/")
    packageTypes <- lapply(paths, read.dcf)
    names(packageTypes) <- .PACKAGE_TYPES
    packageTypes
}
