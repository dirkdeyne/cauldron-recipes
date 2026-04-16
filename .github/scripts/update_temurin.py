"""
Fetches all Eclipse Temurin releases from the endoflife.date API,
derives the Windows x64 JDK ZIP download URL and SHA-256 checksum
from the corresponding GitHub release assets, and writes the result.

Output: java/temurin.json

Tag formats:
  Modern: jdk-25.0.2+10  -> OpenJDK25U-jdk_x64_windows_hotspot_25.0.2_10.zip
  Java 8: jdk8u482-b08   -> OpenJDK8U-jdk_x64_windows_hotspot_8u482b08.zip
"""

import json
import pathlib
import re
import urllib.parse
import urllib.request

EOL_API = "https://endoflife.date/api/v1/products/temurin"
OUTPUT = pathlib.Path("java/temurin.json")

GH_DOWNLOAD = (
    "https://github.com/adoptium/temurin{major}-binaries"
    "/releases/download/{tag}/{filename}"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode()


def _parse_tag(tag: str) -> tuple[str, str] | None:
    """
    Parse a GitHub release tag into (major, filename_stem).

    Modern: 'jdk-25.0.2+10' -> ('25', 'OpenJDK25U-jdk_x64_windows_hotspot_25.0.2_10')
    Java 8: 'jdk8u482-b08'  -> ('8',  'OpenJDK8U-jdk_x64_windows_hotspot_8u482b08')

    Returns None if the tag doesn't match either format.
    """
    # Modern format: jdk-{major}.{minor}.{patch}+{build}
    m = re.fullmatch(r"jdk-(\d+)\.(\d+\.\d+)\+(\d+)", tag)
    if m:
        major, patch, build = m.group(1), m.group(2), m.group(3)
        semver_us = f"{major}.{patch}_{build}"   # e.g. 25.0.2_10
        return major, f"OpenJDK{major}U-jdk_x64_windows_hotspot_{semver_us}"

    # Java 8 format: jdk8u{update}-b{build}
    m = re.fullmatch(r"jdk8u(\d+)-b(\d+)", tag)
    if m:
        update, build = m.group(1), m.group(2)
        return "8", f"OpenJDK8U-jdk_x64_windows_hotspot_8u{update}b{build}"

    return None


def build_entry(version: str, release: dict, fetcher=fetch) -> dict:
    print(f"Retrieving version: {version}")

    gh_url = release.get("latest", {}).get("link")
    if not gh_url:
        print(f"[WARN] No GitHub release link for version {version}")
        return {"version": version, "url": "", "checksums": {}}

    tag_m = re.search(r"/releases/tag/(.+)$", gh_url)
    if not tag_m:
        print(f"[WARN] Could not extract tag from {gh_url}")
        return {"version": version, "url": "", "checksums": {}}

    tag = urllib.parse.unquote(tag_m.group(1))  # decode %2B -> +
    parsed = _parse_tag(tag)
    if not parsed:
        print(f"[WARN] Unexpected tag format: {tag}")
        return {"version": version, "url": "", "checksums": {}}

    major, filename_stem = parsed
    filename = filename_stem + ".zip"
    tag_encoded = tag.replace("+", "%2B")

    dl_url = GH_DOWNLOAD.format(major=major, tag=tag_encoded, filename=filename)
    sha_url = dl_url + ".sha256.txt"

    try:
        sha_text = fetcher(sha_url).strip()
        sha256 = sha_text.split()[0].lower()
    except Exception as e:
        print(f"[WARN] Could not fetch checksum for version {version}: {e}")
        sha256 = None

    checksums = {"SHA-256": sha256} if sha256 else {}
    return {"version": version, "url": dl_url, "checksums": checksums}


def run(fetcher=fetch) -> list:
    data = json.loads(fetcher(EOL_API))
    releases = data.get("result", {}).get("releases", [])

    result = []
    for r in releases:
        if not r.get("name"):
            continue
        entry = build_entry(r["name"], r, fetcher)
        if entry.get("checksums"):
            result.append(entry)

    return result


if __name__ == "__main__":
    results = run()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(results, indent=2) + "\n")
    print(f"Written {len(results)} entries to {OUTPUT}")