"""
Duplicate Finder — finds duplicate files by content.

Usage:
    python finder.py <folder>
    python finder.py <folder> --dry-run
    python finder.py <folder> --delete
    python finder.py --undo [trash_folder]
    python finder.py --empty-trash [trash_folder]

Options:
    <folder>        Folder to scan (recursively)
    --dry-run       Preview only (no actual deletion)
    --delete        Delete duplicates (move to Trash/, keep first in each group)
    --undo          Undo a delete (interactive menu or specific trash folder)
    --empty-trash   Permanently delete from Trash (interactive menu or specific folder)

Reports:
    ~/Desktop/duplicate-finder/Report.txt
    ~/Desktop/duplicate-finder/trash_history.json
    ~/Desktop/duplicate-finder/Trash/YYYY-MM-DD_HH-MM-SS/

See README.md for details.
"""

import argparse
import hashlib
import json
import os
import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path

REPORTS = Path(os.getenv("DUPLICATE_REPORTS", Path.home() / "Desktop" / "duplicate-finder"))
REPORTS.mkdir(parents=True, exist_ok=True)
HISTORY = REPORTS / "trash_history.json"
TRASH = REPORTS / "Trash"

def load_trash_history() -> list:
    if not HISTORY.exists():
        return []
    try:
        with open(HISTORY, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("History file is corrupt, starting again!")
        return []

    if not isinstance(data, list):
        print("History file has invalid format, starting again!")
        return []
    return data  
    
def save_trash_history(data: list) -> None:
    with open(HISTORY, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

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

def delete_duplicates(duplicates, source_folder,dry_run=False):
    now = datetime.now()
    trash_run = TRASH / f'{now:%Y-%m-%d_%H-%M-%S}'
    deleted = []

    for i, group in enumerate(duplicates, start=1):
        keep = group[0]
        print(f'\nGroup {i}:')
        print(f"📌 Keeping: {keep}")
        for f in group[1:]:
            if dry_run:
                print(f"  [DRY-RUN] Would delete {f}")
                continue
            if not f.exists():
                print(f"⚠️ Skipped (not found): {f}")
                continue

            try:
                trash_run.mkdir(parents=True, exist_ok=True)
                trash_file = trash_run / f.name
                counter = 1
                while trash_file.exists():
                    trash_file = trash_run / f"{f.stem}_{counter}{f.suffix}"
                    counter += 1
                shutil.move(str(f), str(trash_file))
                deleted.append({"original": str(f), "trashed": str(trash_file)})
                print(f"  🗑️ Deleted: {f}")
            except OSError as e:
                print(f"  ❌ Failed: {e} | {f}")       
    if deleted:
        history = load_trash_history()
        history.append({
            'date': now.isoformat(),
            'trash_folder': str(trash_run),
            'source_folder': str(source_folder),
            'files': deleted,
        })
        save_trash_history(history)

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

def undo_delete(target=None):
    history = load_trash_history()
    if not history:
        print("No deletes to undo!")
        return

    if target is not None:
        idx = None
        for i, rec in enumerate(history):
            trash_folder_name = Path(rec["trash_folder"]).name

            if trash_folder_name == target:
                idx = i
                break

        if idx is None:
            print(f"❌ No delete record found for: {target}")
            print("   Run `--undo` without arguments to see available deletes.")
            return

        selected = history.pop(idx)

    else:
        print("\nAvailable deletes:\n")
        for i, rec in enumerate(history, start=1):
            date = rec['date'].replace('T', ' ')[:19]
            n_files = len(rec['files'])
            source = rec.get('source_folder', '?')

            total_size = 0
            for f in rec['files']:
                p = Path(f['trashed'])
                if p.exists():
                    total_size += p.stat().st_size

            print(f"  {i}. {date}  ({n_files} files, {format_size(total_size)})")
            print(f"     Source: {source}")
            print(f"     Trash:  {Path(rec['trash_folder']).name}\n")

        choice = input("Select one to undo (number, or 'q' to quit): ").strip()

        if choice.lower() == 'q':
            print('Cancelled')
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(history):
                print(f"❌ Invalid number: {choice}")
                return
        except ValueError:
            print(f"❌ Invalid input: {choice}")
            return

        selected = history.pop(idx)

    print(f"\n↩️ Undoing delete from {selected['date']}")
    if "source_folder" in selected:
        print(f"   Source: {selected['source_folder']}")

    count = 0
    for item in selected['files']:
        src = Path(item['trashed'])
        dst = Path(item['original'])

        if not src.exists():
            print(f"  ⚠️ Missing in trash: {src.name}")
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            print(f"  ↩️ Restored: {dst.name}")
            count += 1
        except OSError as e:
            print(f"  ❌ Failed: {dst} | {e}")

    save_trash_history(history)

    trash_folder = Path(selected['trash_folder'])
    if trash_folder.exists() and not any(trash_folder.iterdir()):
        trash_folder.rmdir()   

    print(f"✅ Restored {count} files")             

def empty_trash(target=None):
    history = load_trash_history()
    if not history:
        print("Nothing to empty — Trash is empty.")
        print("Tip: use `--delete` first to move duplicates to Trash.")
        return

    if target is not None:
        idx = None
        for i, rec in enumerate(history):
            if Path(rec['trash_folder']).name == target:
                idx = i
                break

        if idx is None:
            print(f"❌ No record found for: {target}")
            print("   Run `--empty-trash` without arguments to see contents.")
            return
        
        selected = history.pop(idx)

    else:
        print("\nTrash Contents\n")
        for i, rec in enumerate(history, start=1):
            date = rec['date'].replace('T', ' ')[:19]
            n_files = len(rec['files'])
            source = rec.get('source_folder', '?')

            total_size = 0
            for f in rec['files']:
                p = Path(f['trashed'])
                if p.exists():
                    total_size += p.stat().st_size

            print(f"  {i}. {date}  ({n_files} files, {format_size(total_size)})")
            print(f"     Source: {source}")
            print(f"     Trash:  {Path(rec['trash_folder']).name}\n")

        choice = input("Select one to PERMANENTLY delete (number, or 'q' to quit): ").strip()

        if choice.lower() == 'q':
            print('Cancelled')  
            return

        try:
            idx = int(choice) - 1
            if idx < 0 or idx >= len(history):
                print(f"❌ Invalid number: {choice}")
                return
        except ValueError:
            print(f"❌ Invalid input: {choice}")
            return     
        selected = history.pop(idx)

    n_files = len(selected['files'])
    print(f"\n⚠️  Permanently delete {n_files} files from {Path(selected['trash_folder']).name}?")
    print("   This CANNOT be undone.")
    confirm = input("Type 'yes' to confirm: ").strip().lower()

    if confirm != 'yes':
        print('Cancelled')
        history.insert(idx ,selected)
        save_trash_history(history)
        return

    count = 0
    for item in selected['files']:
        p = Path(item['trashed'])
        if p.exists():
            try:
                p.unlink()
                count += 1
            except OSError as e:
                print(f"  ❌ Failed: {p.name} | {e}")   

    trash_folder = Path(selected['trash_folder'])
    if trash_folder.exists() and not any(trash_folder.iterdir()):
        trash_folder.rmdir()

    save_trash_history(history)
    print(f"🗑️ Permanently deleted {count} files")              

def main():
    parser = argparse.ArgumentParser(description="Code finds duplicate files")
    parser.add_argument(
        'folder',
        nargs='?',
        help='Folder To Scan')
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Shows the files that would be deleted(NOT ACTUAL!)')
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Deletes duplicate files')
    parser.add_argument(
        '--undo',
        nargs='?',
        const=True,
        default=False,
        metavar='TRASH_FOLDER',
        help='Undo a delete (interactive menu, or specify trash folder name)')
    parser.add_argument(
        '--empty-trash',
        nargs='?',
        const=True,
        default=False,
        metavar='TRASH_FOLDER',
        help='Permanently delete trash (interactive menu, or specify trash folder name)'
    )

    args = parser.parse_args()

    if args.empty_trash:
        if args.empty_trash is True:
            empty_trash()
        else:
            empty_trash(args.empty_trash)
        return        

    if args.undo:
        if args.undo is True:
            undo_delete()
        else:
            undo_delete(args.undo)
        return
    
    if args.folder is None:
        print("❌ Error: folder is required.")
        return
    
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
        delete_duplicates(duplicates, folder,dry_run=args.dry_run)


if __name__ == "__main__":
    main()
