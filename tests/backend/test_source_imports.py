import subprocess
import sys
from pathlib import Path


def test_source_backend_can_import_collector_outside_repo(tmp_path):
    backend = Path(__file__).resolve().parents[2] / "backend"
    script = '''
import runpy, sys
from pathlib import Path
Path.home = classmethod(lambda cls: Path(sys.argv[2]))
sys.path.insert(0, sys.argv[1])
runpy.run_path(str(Path(sys.argv[1]) / "main.py"), run_name="import_check")
import cli.collect_jobs
assert callable(cli.collect_jobs.collect_for_title)
'''
    result = subprocess.run([sys.executable, "-c", script, str(backend), str(tmp_path)],
                            cwd=tmp_path, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
