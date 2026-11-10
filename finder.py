"""
Duplicate Finder — finds duplicate files by content.

Scans a folder recursively, groups files by size, then hashes only
suspicious files (same size) to detect duplicates by SHA-256 content.

Usage:
    python finder.py <folder>
    python finder.py <folder> --dry-run
    python finder.py <folder> --delete

Options:
    <folder>      Folder to scan (recursively)
    --dry-run     Show what would be deleted (no actual deletion)
    --delete      Delete duplicate files (keeps first file in each group)

Reports:
    Results are appended to ~/Desktop/duplicate-finder/Report.txt
    (override with the DUPLICATE_REPORTS environment variable).

See README.md for details.
"""

import argparse
import hashlib
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPORTS = Path(os.getenv("DUPLICATE_REPORTS", Path.home() / "Desktop" / "duplicate-finder"))
REPORTS.mkdir(parents=True, exist_ok=True)

def file_hash(path, size=8192):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while True:
            chunk = f.read(size)
            if not chunk:
                break
            h.update(chunk)
        return h.hexdigest()

def format_size(bytes_size):
    if bytes_size < 1024:
        return f'{bytes_size} B'
    elif bytes_size < 1024 ** 2:
        return f'{(bytes_size / 1024):.1f} KB'
    elif bytes_size < 1024 ** 3:
        return f'{(bytes_size / 1024 ** 2):.1f} MB'
    elif bytes_size < 1024 ** 4:
        return f'{(bytes_size / 1024 ** 3):.1f} GB'
    else:
        return f'{(bytes_size / 1024 ** 4):.1f} TB'

def group_by_size(paths):
    groups = defaultdict(list)
    for path in paths:
        try:
            if not path.is_file():
                continue
            size = path.stat().st_size
            groups[size].append(path)
        except OSError:
            continue
    return groups
    
def find_duplicates(folder):
    folder = Path(folder)
    all_files = []
    for path in folder.rglob("*"):
        if path.is_file() and not path.is_symlink():
            all_files.append(path)

    groups = group_by_size(all_files)

    suspicious = [g for g in groups.values() if len(g) > 1]

    by_hash = defaultdict(list)
    for group in suspicious:
        for f in group:
            try:
                h = file_hash(f)
                by_hash[h].append(f)
            except OSError:
                continue

    duplicates = [g for g in by_hash.values() if len(g) > 1]
    duplicates.sort(key=lambda g: g[0].stat().st_size, reverse=True)
    return duplicates   

def delete_duplicates(duplicates, dry_run=False):
    for i, group in enumerate(duplicates, start=1):
        keep = group[0]
        print(f'\nGroup {i}:')
        print(f"📌 Keeping: {keep}")
        for f in group[1:]:
            if dry_run:
                print(f"  [DRY-RUN] Would delete {f}")
            else:
                try:
                    if not f.exists():
                        print(f"⚠️ Skipped (not found): {f}")
                        continue
                    f.unlink()
                    print(f"  🗑️ Deleted: {f}")
                except OSError as e:
                    print(f'❌ Failed: {e} | {f}')   

def print_report(duplicates, folder):
    now = datetime.now()
    lines = [
        "=" * 60,
        f"Scanned at: {now:%Y-%m-%d %H:%M:%S}",
        f"Folder: {folder}",
        "=" * 60,
    ]

    if not duplicates:
        lines.append("✅ No duplicates found!")
    else:
        lines.append(f"Found {len(duplicates)} groups of duplicates:")
        lines.append("")
        for i, group in enumerate(duplicates, start=1):
            size = group[0].stat().st_size
            lines.append(f"Group {i} ({format_size(size)}, {len(group)} files):")
            for f in group:
                lines.append(f"  {f}")
            lines.append("")

        total_files =  sum(len(g) for g in duplicates)
        total_wasted = sum(g[0].stat().st_size * (len(g) - 1) for g in duplicates)
        lines.append("─" * 60)
        lines.append(f"Total duplicates: {total_files} files")
        lines.append(f"Wasted space: {format_size(total_wasted)}")
        lines.append("=" * 60)

    lines.append("")

    print("\n".join(lines))

    log = REPORTS / "Report.txt"
    with open(log, 'a', encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"📄 Report: {log}")  

def main():
    parser = argparse.ArgumentParser(description="Code finds duplicate files")
    parser.add_argument('folder', help='Folder To Scan')
    parser.add_argument('--dry-run', action='store_true', help='Shows the files that would be deleted(NOT ACTUAL!)')
    parser.add_argument('--delete', action='store_true', help='Deletes duplicate files')

    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"❌ Folder not found: {folder}")
        return
    if not folder.is_dir():
        print(f"❌ Not a folder: {folder}")
        return

    duplicates = find_duplicates(folder)
    print_report(duplicates, folder)

    if (args.dry_run or args.delete) and duplicates:
        label = "Would delete" if args.dry_run else "Deleting"
        print(f"\n🗑️ {label} duplicates...")
        delete_duplicates(duplicates, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
