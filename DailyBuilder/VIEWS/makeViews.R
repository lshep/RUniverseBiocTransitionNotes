.wrap_field <- function(x, width = 78, indent = 8) {
    if (length(x) == 0 || is.na(x)) {
        return(NA_character_)
    }
    paste(
        strwrap(x, width = width, exdent = indent),
        collapse = "\n"
    )
}

.fmt_deps <- function(deps, role) {
    x <- deps[deps$role == role, ]
    if (!nrow(x)) {
        return(NULL)
    }

    paste(
        ifelse(
            is.na(x$version),
            x$package,
            paste0(x$package, " (", x$version, ")")
        ),
        collapse = ", "
    )
}

.fmt_rel_paths <- function(x, field, pkg) {
    if (length(x) == 0) {
        return(NA_character_)
    }
    paste0(
        paste0(
            "vignettes/",
            pkg,
            "/inst/doc/",
            x[[field]]
        ),
        collapse = ",\n\t"
    )
}

.fmt_titles <- function(x) {
    if (length(x) == 0) {
        return(NA_character_)
    }
    paste0(x$title, collapse = ",\n\t")
}

.has <- function(x, a_file) {
    if (length(x) == 0) {
        return(NA_character_)
    }
    any(
        grepl(
            a_file,
            x
        )
    )
}

#' Prepare package VIEW data
#'
#' @description Prepare the VIEW of a package. Does not include
#' source, binary, extra doc, Rfiles, and reverse dependency fields.
#'
#' @param df api data
#'
#' @returns a list of named fields for a package VIEW entry in the VIEWS
#' file
#'
#' @examples
#' df <- getRuDf(pkg, branch)
#' prepareView(df)
#'
#' @export
prepareView <- function(df) {
    fields <- list(
        Package = df$Package,
        Version = df$Version,
        Depends = .fmt_deps(df$`_dependencies`, "Depends"),
        Imports = .fmt_deps(df$`_dependencies`, "Imports"),
        Suggests = .fmt_deps(df$`_dependencies`, "Suggests"),
        LinkingTo = .fmt_deps(df$`_dependencies`, "LinkingTo"),
        License = df$License,
        SystemRequirements = df$SystemRequirements,
        MD5sum = df$MD5sum,
        NeedsCompilation = df$NeedsCompilation,
        Archs = df$arches,
        Title = df$Title,
        Description = .wrap_field(df$Description),
        biocViews = df$biocViews,
        Author = gsub("\n|\\s+", " ", wrap_field(df$Author)),
        Maintainer = df$Maintainer,
        URL = df$URL,
        VignetteBuilder = df$VignetteBuilder,
        Video = df$Video,
        BugReports = df$BugReports,
        PackageStatus = df$PackageStatus, # deprecated packages removed immediately
        git_url = df$`_upstream`,
        git_branch = df$`_bioc`$branch[2], # release branch
        git_last_commit = df$RemoteSha,
        git_last_commit_date = substr(df$`Date/Publication`, 1, 10),
        `Date/Publication` = substr(df$`Date/Publication`, 1, 10),
        `Config/Bioconductor/UnsupportedPlatforms` = df$`UnsupportedPlatforms`,
        vignettes = .fmt_rel_paths(df$`_vignettes`, "filename", df$Package),
        vignetteTitles = .fmt_titles(df$`_vignettes`),
        hasREADME = .has(df$`_assets`, "readme.md"),
        hasNEWS = .has(df$`_assets`, "news.txt"),
        hasLICENSE = .has(df$`_assets`, "LICENSE")
        # Rfiles = Is this useful? (Do people use them?)
        # hasINSTALL = how does RU handle system requirements (esp., mac, win), can it go away?
    )

    fields[!vapply(fields, is.null, logical(1))]
}

#' @examples
#' df <- prepareView(pkg, branch)
#' writeView(df, tempfile())
#'
#' @export
writeView <- function(df, save_path, ext = c("json", "dcf")) {
    .save_as(df, save_path, ext)
}

readView <- function(package, path) {
    jsonlite::read_json(file.path(path, paste0(package, ".json")))
}

readViews <- function(package_type, save_path, ext = c("json", "dcf")) {
    pkgs <- getPackagesByType(package_type)
    views <- lapply(pkgs, function(x) readView(x, save_path))
    jsonlite::toJSON(views)
}