import argparse
import hashlib
import os
import json
import shutil
import sys
import time
import zipfile
from pathlib import Path
from datetime import datetime
from typing import List,Dict,Tuple
from colorama import init, Fore, Style
init(autoreset=True) 


File_TYPES: Dict[str,List[str]] = {
    "images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp", ".svg", ".heic"],
    "documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".md", ".ppt", ".pptx", ".xls", ".xlsx", ".csv"],
    "videos": [".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm"],
    "audio": [".mp3", ".wav", ".aac", ".flac", ".ogg", ".m4a"],
    "archives": [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2"],
    "code": [".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".c", ".cpp", ".cs", ".go", ".rb", ".php", ".html", ".css", ".json", ".sql", ".sh", ".bat"],
    "design": [".psd", ".ai", ".xd", ".fig", ".sketch"],
}

LOG_NAME = ".organizer_log.json"
REPORT_NAME = ".organizer_report.json"
DUP_DIR = "duplicates"

def humanize(n:int) -> str:
    return f"{n:,}"

def iter_files(root: Path): 
    for path in root.iterdir():
        if path.is_dir():
            yield from iter_files(path)
        else:
            yield path


def detect_category(file_path: Path) -> str:
    ext = file_path.suffix.lower()  # <-- এইটা ঠিক
    for category, extensions in File_TYPES.items():
        if ext in extensions:
            return category
    return "others"


def md5sum(path: Path, chunk: int = 1024*1024) -> str:
   h = hashlib.md5()
   with path.open("rb") as f:
       while True:
           data = f.read(chunk)
           if not data:
               break
           h.update(data)
   return h.hexdigest()
    

def date_parts(path: Path) -> Tuple[str, str]:
    """
    Returns (YYYY, MM) using file's creation time if available, else modified time.
    """
    try:
        ts = path.stat().st_ctime
    except Exception:
        ts = path.stat().st_mtime
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y"), dt.strftime("%m")


def ensure_dir(path: Path, dry: bool):
    if dry:
        return
    path.mkdir(parents=True, exist_ok=True)


def move_file(src: Path, dst: Path, dry: bool):
    ensure_dir(dst.parent, dry)
    if dry:
        return
   
    if dst.exists():
        stem, suf = dst.stem, dst.suffix
        i = 1
        while True:
            candidate = dst.with_name(f"{stem} ({i}){suf}")
            if not candidate.exists():
                dst = candidate
                break
            i += 1
    shutil.move(str(src), str(dst))


def load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def save_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def organize(target: Path, by_date: bool, dry_run: bool) -> None:
    if not target.exists() or not target.is_dir():
        print(f"{Fore.RED}❌ Path not found or not a directory: {target}")
        sys.exit(1)

    print(f"{Fore.RED}{Style.BRIGHT}🗂️  Organizing: {target.resolve()}")
    if dry_run:
        print(f"{Fore.YELLOW}🔎 Dry-run mode: no files will be moved.\n")

    files = list(iter_files(target))
    total = len(files)
    if total == 0:
        print(f"{Fore.MAGENTA}ℹ️  No files found in the target folder.")
        return

    seen_hashes: Dict[str, Path] = {}
    summary: Dict[str, int] = {}
    duplicates: List[Dict[str, str]] = []
    moves_log: List[Dict[str, str]] = []

    dup_dir = target / DUP_DIR
    ensure_dir(dup_dir, dry_run)

    start = time.time()

    for f in files:
        if f.name in {LOG_NAME, REPORT_NAME} or f.parent == dup_dir or f.name == DUP_DIR:
            continue

        try:
            file_hash = md5sum(f)
        except Exception as e:
            print(f"{Fore.YELLOW}⚠️  Skipping (hash error): {f.name} ({e})")
            continue

        if file_hash in seen_hashes:
            dst = dup_dir / f.name
            move_file(f, dst, dry_run)
            duplicates.append({"src": str(f), "dst": str(dst)})
            if not dry_run:
                moves_log.append({"src": str(f), "dst": str(dst)})
            print(f"{Fore.RED}💾 Duplicate moved: {f.name}")
            continue
        else:
            seen_hashes[file_hash] = f

        cat = detect_category(f)
        summary[cat] = summary.get(cat, 0) + 1

        if by_date:
            yyyy, mm = date_parts(f)
            dst = target / cat / yyyy / mm / f.name
        else:
            dst = target / cat / f.name

        if f == dst:
            continue

        move_file(f, dst, dry_run)
        if not dry_run:
            moves_log.append({"src": str(f), "dst": str(dst)})
        print(f"{Fore.GREEN}✅ Moved: {f.name} → {dst}")

    elapsed = time.time() - start

    if not dry_run:
        save_json(target / LOG_NAME, {"moves": moves_log})
        save_json(
            target / REPORT_NAME,
            {
                "target": str(target.resolve()),
                "summary": summary,
                "duplicates_moved": len(duplicates),
                "moves_total": len(moves_log),
                "by_date": by_date,
                "timestamp": datetime.now().isoformat(timespec="seconds"),
                "elapsed_seconds": round(elapsed, 2),
            },
        )

    organized = sum(summary.values())
    print(f"\n{Fore.YELLOW}✅ Organization complete!" if not dry_run else f"\n{Fore.YELLOW}✅ Dry-run summary")
    print(f"   • Scanned files      : {Fore.MAGENTA}{humanize(total)}{Style.RESET_ALL}")
    print(f"   • Organized (kept)   : {Fore.GREEN}{humanize(organized)}{Style.RESET_ALL}")
    print(f"   • Duplicates moved   : {Fore.RED}{humanize(len(duplicates))}{Style.RESET_ALL}")
    if summary:
        print("   • Breakdown by category:")
        for cat, n in sorted(summary.items(), key=lambda x: (-x[1], x[0])):
            print(f"     - {Fore.CYAN}{cat:<10}{Style.RESET_ALL} → {Fore.GREEN}{humanize(n)}{Style.RESET_ALL}")
    print(f"\n⏱️  Time taken: {Fore.MAGENTA}{elapsed:.2f}s{Style.RESET_ALL}")
    if not dry_run:
        print(f"🧾 Report saved: {Fore.WHITE}{REPORT_NAME}{Style.RESET_ALL}")
        # print(f"🪵 Undo log   : {Fore.WHITE}{LOG_NAME}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW} {Style.BRIGHT}✨Thank You!{Style.RESET_ALL}")


def undo_last(target: Path, dry_run: bool) -> None:
    log_path = target / LOG_NAME
    if not log_path.exists():
        print("ℹ️  No organizer log found. Nothing to undo.")
        return

    data = load_json(log_path, {"moves": []})
    moves = data.get("moves", [])
    if not moves:
        print("ℹ️  Log is empty. Nothing to undo.")
        return

    print(f"↩️  Undoing {len(moves)} moves...")
    reverted = 0
    for m in reversed(moves):
        src = Path(m["dst"]) 
        dst = Path(m["src"]) 

        if not src.exists():
            
            continue

        ensure_dir(dst.parent, dry_run)
        if dry_run:
            reverted += 1
            continue

    
        final_dst = dst
        if final_dst.exists():
            stem, suf = final_dst.stem, final_dst.suffix
            i = 1
            while True:
                candidate = final_dst.with_name(f"{stem}.undo{'' if i == 1 else i}{suf}")
                if not candidate.exists():
                    final_dst = candidate
                    break
                i += 1

        shutil.move(str(src), str(final_dst))
        reverted += 1

    if not dry_run:
        save_json(log_path, {"moves": []})

    print(f"✅ Undo complete. Files restored (or renamed with .undo): {reverted}")


def build_parser():
    p = argparse.ArgumentParser(
        description="Organize files into categories, detect duplicates, and generate a summary report."
    )
    sub = p.add_subparsers(dest="command", required=True)

    o = sub.add_parser("organize", help="Organize files in the target folder")
    o.add_argument("--path", required=True, help="Target folder path")
    o.add_argument("--by-date", action="store_true", help="Nest inside YYYY/MM folders")
    o.add_argument("--dry-run", action="store_true", help="Show what would happen without moving files")

    u = sub.add_parser("undo", help="Undo the last organization run (uses .organizer_log.json)")
    u.add_argument("--path", required=True, help="Target folder path")
    u.add_argument("--dry-run", action="store_true", help="Preview undo operations without moving files")

    return p


def main():
    parser = build_parser()
    args = parser.parse_args()
    raw_path = args.path.replace("\\", "/") 
    target = Path(os.path.expanduser(raw_path)).resolve()

    if args.command == "organize":
        organize(target, by_date=args.by_date, dry_run=args.dry_run)
    elif args.command == "undo":
        undo_last(target, dry_run=args.dry_run)
    else:
        parser.print_help()



if __name__ == "__main__":
    main()