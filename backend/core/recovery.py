"""Daily local recovery copy; never resets or automatically replaces live data."""
import shutil
import sqlite3
from datetime import datetime, timezone

from core.config import get_data_dir


def snapshot():
    source=get_data_dir()
    target=source/'recovery-backups'/datetime.now(timezone.utc).strftime('daily-%Y%m%d')
    if target.exists():
        return
    staging=target.with_name(target.name+'-building')
    staging.mkdir(exist_ok=True)
    for name in ('langhire.db','memory_store.db'):
        if (source/name).is_file():
            with sqlite3.connect((source/name).as_uri()+'?mode=ro',uri=True) as src, sqlite3.connect(staging/name) as dst:
                src.backup(dst)
    for name in ('candidate_profile.json','settings.json','qa_repository.json'):
        if (source/name).is_file():
            shutil.copy2(source/name,staging/name)
    for name in ('resumes','tailored_resumes','application_documents'):
        if (source/name).is_dir():
            shutil.copytree(source/name,staging/name,dirs_exist_ok=True)
    staging.rename(target)
