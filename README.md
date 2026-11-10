# Duplicate Finder

Find and delete duplicate files by content (not name).

## Features

- Finds duplicates by **SHA-256 hash** (content-based)
- Fast: groups by size first, hashes only suspicious files
- Safe: `--dry-run` previews without deleting
- Report saved to `Report.txt`
- No external dependencies (stdlib only)

## How it works

1. Collects all files recursively
2. Groups by exact file size (fast filter)
3. Hashes only files with matching sizes
4. Groups by hash — same hash = duplicate

## Requirements

- Python 3.10+

## Usage

### Report only

```bash
python finder.py <folder> --dry-run
python finder.py <folder> --delete