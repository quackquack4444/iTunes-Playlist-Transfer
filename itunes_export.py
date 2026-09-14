#!/usr/bin/env python3
"""
itunes_export.py

1. Reads an iTunes "Library.xml" file.
2. Finds a named playlist FOLDER inside it.
3. Exports every playlist inside that folder (including nested sub-folders)
   as a raw .m3u, using the same style as your manually-made playlists
   (M:\\Music\\Music\\... paths, "#EXTINF:<secs>,<Title> - <Artist>").
4. Converts each of those straight into the player's format
   (syncr/... paths, #EXTALB tags, UTF-8 .m3u8 with BOM) --
   same logic as convert_playlists.py.

Usage:
    python itunes_export.py --xml "G:\\Music\\iTunes Library.xml" --folder "U-playlists to export as m3u"

Optional:
    --raw-dir DIR         where the intermediate raw .m3u files are written
                          (default: ./raw_export)
    --output-dir DIR      where the final converted .m3u8 files are written
                          (default: ./converted)
    --no-recursive        only export playlists directly inside the folder,
                          not ones inside nested sub-folders
"""

import argparse
import plistlib
import sys
from pathlib import Path
from urllib.parse import urlparse, unquote

# ---- Settings shared with convert_playlists.py ----
SOURCE_PREFIX = r"M:\Music\Music\\"
DEST_PREFIX = "syncr/"


# ---------------------------------------------------------------------------
# Step 1: read the iTunes XML
# ---------------------------------------------------------------------------

def load_library(xml_path: Path) -> dict:
    with open(xml_path, "rb") as f:
        return plistlib.load(f)


def location_to_windows_path(location: str) -> str:
    """Convert an iTunes 'file://localhost/M:/Music/...' URL to M:\\Music\\..."""
    parsed = urlparse(location)
    path = unquote(parsed.path)
    if path.startswith("/") and len(path) > 2 and path[2] == ":":
        # "/M:/Music/..." -> "M:/Music/..."
        path = path[1:]
    return path.replace("/", "\\")


def find_folder_persistent_id(playlists: list, folder_name: str) -> str:
    for p in playlists:
        if p.get("Folder") and p.get("Name", "").strip().lower() == folder_name.strip().lower():
            return p["Playlist Persistent ID"]
    raise SystemExit(f"Could not find a playlist FOLDER named '{folder_name}' in the library.")


def collect_playlists_in_folder(playlists: list, folder_pid: str, recursive: bool = True) -> list:
    """Return all non-folder playlist entries that live inside folder_pid,
    optionally including those nested inside sub-folders."""
    by_parent: dict[str, list] = {}
    for p in playlists:
        parent = p.get("Parent Persistent ID")
        by_parent.setdefault(parent, []).append(p)

    result = []
    stack = [folder_pid]
    while stack:
        pid = stack.pop()
        for child in by_parent.get(pid, []):
            if child.get("Folder"):
                if recursive:
                    stack.append(child["Playlist Persistent ID"])
            else:
                result.append(child)
    return result


def safe_filename(name: str) -> str:
    bad = '<>:"/\\|?*'
    return "".join("_" if c in bad else c for c in name).strip()


def build_raw_m3u(playlist: dict, tracks: dict) -> str:
    lines = ["#EXTM3U"]
    for item in playlist.get("Playlist Items", []):
        track_id = str(item.get("Track ID"))
        track = tracks.get(track_id)
        if not track:
            continue
        location = track.get("Location")
        if not location:
            continue  # e.g. a track that's not on disk (streaming/missing)

        title = track.get("Name", "")
        artist = track.get("Artist", "")
        duration_s = round(track.get("Total Time", 0) / 1000)
        win_path = location_to_windows_path(location)

        lines.append(f"#EXTINF:{duration_s},{title} - {artist}")
        lines.append(win_path)
    return "\r\n".join(lines) + "\r\n"


# ---------------------------------------------------------------------------
# Step 2: convert raw m3u text -> syncr/ format (same logic as convert_playlists.py)
# ---------------------------------------------------------------------------

def convert_path_line(line: str) -> tuple[str, str]:
    stripped = line.strip()
    prefix_variants = [SOURCE_PREFIX, SOURCE_PREFIX.rstrip("\\")]
    rel = stripped
    for pv in prefix_variants:
        if rel.lower().startswith(pv.lower()):
            rel = rel[len(pv):]
            break
    rel = rel.replace("\\", "/").lstrip("/")
    new_line = DEST_PREFIX + rel
    parts = rel.split("/")
    album = parts[-2] if len(parts) >= 2 else ""
    return new_line, album


def convert_playlist_text(text: str) -> str:
    out_lines = []
    for line in text.splitlines():
        if not line.strip():
            continue
        if line.startswith("#EXTM3U"):
            out_lines.append("#EXTM3U")
        elif line.startswith("#EXTINF"):
            out_lines.append(line.strip())
        elif line.startswith("#"):
            out_lines.append(line.strip())
        else:
            new_path, album = convert_path_line(line)
            if album:
                out_lines.append(f"#EXTALB:{album}")
            out_lines.append(new_path)
    return "\n".join(out_lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, help="Path to iTunes Library.xml")
    parser.add_argument("--folder", required=True, help="Name of the playlist folder to export")
    parser.add_argument("--raw-dir", default="raw_export", help="Where to write intermediate raw .m3u files")
    parser.add_argument("--output-dir", default="converted", help="Where to write final syncr/ .m3u8 files")
    parser.add_argument("--no-recursive", action="store_true", help="Don't descend into nested sub-folders")
    args = parser.parse_args()

    xml_path = Path(args.xml)
    if not xml_path.exists():
        raise SystemExit(f"File not found: {xml_path}")

    lib = load_library(xml_path)
    tracks = lib.get("Tracks", {})
    playlists = lib.get("Playlists", [])

    folder_pid = find_folder_persistent_id(playlists, args.folder)
    target_playlists = collect_playlists_in_folder(playlists, folder_pid, recursive=not args.no_recursive)

    if not target_playlists:
        print(f"No playlists found inside folder '{args.folder}'.")
        return

    raw_dir = Path(args.raw_dir)
    out_dir = Path(args.output_dir)
    raw_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    for playlist in target_playlists:
        name = playlist.get("Name", "Untitled")
        fname = safe_filename(name)

        raw_text = build_raw_m3u(playlist, tracks)
        raw_path = raw_dir / f"{fname}.m3u"
        raw_path.write_text(raw_text, encoding="utf-8", newline="")

        converted = convert_playlist_text(raw_text)
        out_path = out_dir / f"{fname}.m3u8"
        out_path.write_bytes(("\ufeff" + converted).encode("utf-8"))

        n_tracks = converted.count(DEST_PREFIX)
        print(f"{name}: {n_tracks} tracks -> {raw_path.name}, {out_path.name}")


if __name__ == "__main__":
    main()
