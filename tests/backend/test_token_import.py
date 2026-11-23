import os
import subprocess
import sys
from pathlib import Path


def test_import_does_not_overwrite_running_token(tmp_path):
    token=tmp_path/'.api_token';token.write_text('running-token')
    env={**os.environ,'LANGHIRE_DATA_DIR':str(tmp_path),'LANGHIRE_NO_WATCHDOG':'1'}
    env.pop('LANGHIRE_API_TOKEN',None)
    result=subprocess.run([sys.executable,'-c',"import sys; sys.path.insert(0,'backend'); import main"],
                          cwd=Path(__file__).resolve().parents[2],env=env,capture_output=True,timeout=45)
    assert result.returncode==0,result.stderr.decode(errors='replace')
    assert token.read_text()=='running-token'
