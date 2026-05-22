





# ------------------------------
# Parse R-Universe Package API
#   For Build Results from SPB 
# ------------------------------
def parse_runiverse_build(pkg):
    # -----------------------------
    # Platform policy
    # -----------------------------
    platforms_ok = ["source"]
    platforms_warnings = ["bioc-check", "linux", "macos", "windows"]
    ALWAYS_KEEP = ["source", "bioc-check"]
    url = f"https://{SPB_RUNIVERSE}.r-universe.dev/api/packages/{pkg}"

    build_clean = True

    bioc_r_version = None
    try:
        cfg_url = "https://bioconductor.org/config.yaml"
        cfg_resp = requests.get(cfg_url, timeout=30)
        cfg_resp.raise_for_status()

        config = yaml.safe_load(cfg_resp.text)
        single_pkg = config.get("single_package_builder", {})
        bioc_r_version = single_pkg.get("r_version")

        print(f"[DEBUG] Bioconductor R version: {bioc_r_version}")

    except Exception as e:
        print(f"[WARN] Could not fetch Bioconductor config, skipping R filtering: {e}")

    try:
        resp = requests.get(url, headers=BIOC_STAGING_HEADERS, timeout=10)

        if resp.status_code == 404:
            return {
                "status": ["ERROR"],
                "message": f"❌ Package `{pkg}` not available in R-universe (likely build failure)",
                "_build_clean": False
            }

        resp.raise_for_status()
        data = resp.json()

    except requests.RequestException as e:
        return {
            "status": ["UNKNOWN"],
            "message": f"⚠️ Could not fetch R-universe data for `{pkg}`",
            "_build_clean": False
        }

    build_url = data.get("_buildurl")

    # -----------------------------
    # HARD FAILURE CASE 
    # -----------------------------
    failure_msg = data.get("_failure")
    if failure_msg:
        fail_build_url = failure_msg.get("buildurl") or build_url

        table = (
            "| Platform | R | Status | URL |\n"
            "|----------|---|--------|------|\n"
            f"| ❌ build | — | ❌ BUILD FAILED | "
            f"{f'[run]({fail_build_url})' if fail_build_url else ''} |"
        )

        return {
            "status": ["ERROR"],
            "message": (
                f"🚨 R-universe build failed for `{pkg}` "
                f"(no check results available)\n\n{table}"
            ),
            "_build_clean": False
        }

    jobs = data.get("_jobs", [])


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
