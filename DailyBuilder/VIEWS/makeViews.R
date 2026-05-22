library(jsonlite)

url <- "https://bioc.r-universe.dev/api/packages/BiocCheck"
data <- fromJSON(url)


wrap_dcf <- function(x, width = 78, indent = 8) {
  if (length(x) == 0 || is.na(x)) return(NA_character_)
  paste(
    strwrap(x, width = width, exdent = indent),
    collapse = "\n"
  )
}


deps <- data$`_dependencies`

fmt_deps <- function(role) {
  x <- deps[deps$role == role, ]
  if (!nrow(x)) return(NULL)

  paste(
    ifelse(
      is.na(x$version),
      x$package,
      paste0(x$package, " (", x$version, ")")
    ),
    collapse = ", "
  )
}

Depends  <- fmt_deps("Depends")
Imports  <- fmt_deps("Imports")
Suggests <- fmt_deps("Suggests")

dcf <- list(
  Package = data$Package,
  Version = data$Version,
  Depends = Depends,
  Imports = Imports,
  Suggests = Suggests,
  License = data$License,
  MD5sum = data$MD5sum,
  NeedsCompilation = data$NeedsCompilation,
  Title = data$Title,
  Description = wrap_dcf(data$Description),
  biocViews = data$biocViews,
  Author = wrap_dcf(data$Author),
  Maintainer = data$Maintainer,
  URL = data$URL,
  VignetteBuilder = data$VignetteBuilder,
  BugReports = data$BugReports,
  git_url = data$`_upstream`,
  git_branch = data$`_bioc`$branch[2],  # release branch
  git_last_commit = data$RemoteSha,
  git_last_commit_date = substr(data$`Date/Publication`, 1, 10),
  `Date/Publication` = substr(data$`Date/Publication`, 1, 10)
)

dcf <- dcf[!vapply(dcf, is.null, logical(1))]




### This would not include the source/binary information, extra doc, reverse
### depends
### can we get these from other apis?
