# Duplicate Finder

Find and safely delete duplicate files by content (SHA-256 hash), not by name.

## Features

- **Content-based detection** — finds duplicates even if filenames differ
- **Fast** — groups by size first, hashes only suspicious files
- **Safe delete** — deleted files go to `Trash/`, not permanently removed
- **Undo** — restore from Trash with an interactive menu
- **Selective empty-trash** — permanently delete specific delete sessions
- **Dry-run** — preview without touching any file
- **Reports** — full log saved to `Report.txt`
- **No external dependencies** — Python stdlib only

## How it works

1. Recursively collects all files in the target folder
2. Groups files by **exact size** (fast filter)
3. Hashes only files with matching sizes (SHA-256)
4. Groups files by hash — same hash = duplicate
5. On `--delete`, moves duplicates to `Trash/YYYY-MM-DD_HH-MM-SS/`

## Requirements

- Python 3.10+

```bash
python finder.py <folder>
python finder.py <folder> --dry-run
python finder.py <folder> --delete
python finder.py --undo [trash_folder]
python finder.py --empty-trash [trash_folder]