import sqlite3
from pathlib import Path

from core import recovery


def test_backup_closes_databases_before_renaming_directory(data_dir,monkeypatch):
    source=sqlite3.connect(data_dir/'langhire.db')
    source.execute('create table example(value text)');source.execute("insert into example values ('kept')")
    source.commit();source.close()
    connections=[];connect=sqlite3.connect;rename=Path.rename
    class Tracked(sqlite3.Connection):
        closed=False
        def close(self):
            self.closed=True
            return super().close()
    def tracked(*args,**kwargs):
        connection=connect(*args,**kwargs,factory=Tracked);connections.append(connection);return connection
    def checked_rename(path,target):
        assert connections and all(connection.closed for connection in connections)
        return rename(path,target)
    monkeypatch.setattr(recovery.sqlite3,'connect',tracked)
    monkeypatch.setattr(Path,'rename',checked_rename)
    recovery.snapshot()
    backup=next((data_dir/'recovery-backups').glob('daily-*'))
    restored=connect(backup/'langhire.db')
    try:assert restored.execute('select value from example').fetchone()[0]=='kept'
    finally:restored.close()
