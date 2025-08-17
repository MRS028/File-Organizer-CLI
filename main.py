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