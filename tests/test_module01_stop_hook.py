import json
import os
import subprocess
import sys
import tempfile
import sqlite3
from contextlib import closing
from pathlib import Path


def test_hook_continues_once_for_same_state():
    root = Path(__file__).resolve().parents[1]
    scripts = root / "codex-skill" / "review-harness" / "scripts"
    env = dict(os.environ, REVIEW_HARNESS_HOME=str(root), CODEX_SESSION_ID="test_session")
    with tempfile.TemporaryDirectory() as temp:
        def run(*args):
            return subprocess.run([sys.executable, str(scripts / "run_review_harness.py"), *args], cwd=temp, env=env, text=True, capture_output=True, check=True)
        run("init-db")
        run("create-run", "--topic", "test topic", "--profile", str(root / "examples" / "uv-miniature-computational-spectrometer.topic-profile.json"))
        def hook(session):
            proc = subprocess.run([sys.executable, str(scripts / "module01_stop_hook.py")], cwd=temp, env=env, input=json.dumps({"session_id": session, "cwd": temp}), text=True, capture_output=True, check=True)
            return json.loads(proc.stdout)
        assert hook("other_session") == {}
        assert hook("test_session")["decision"] == "block"
        assert hook("test_session") == {}
        db = Path(temp) / "runtime" / "research.sqlite3"
        with closing(sqlite3.connect(db)) as con, con:
            run_id = con.execute("select id from topic_runs").fetchone()[0]
            con.execute("insert into decisions (id,topic_run_id,agent_recommendation,user_decision,decision_actor,module_02_permitted,notes,decided_at) values ('d',?,'recommended','approved','agent',1,'ok','2026')", (run_id,))
            con.execute("create table module02_runs (id text, topic_run_id text)")
            con.execute("create table module03_outline_runs (id text, module02_run_id text, updated_at text)")
            con.execute("create table module04_manuscript_runs (id text, module03_run_id text, status text, updated_at text)")
            con.execute("insert into module02_runs values ('m2',?)", (run_id,))
            con.execute("insert into module03_outline_runs values ('m3','m2','2026')")
            con.execute("insert into module04_manuscript_runs values ('m4','m3','drafting_manuscript','2026')")
        assert "write_complete_manuscript" in hook("test_session")["reason"]
        with closing(sqlite3.connect(db)) as con, con:
            con.execute("update module04_manuscript_runs set status='completed'")
        assert hook("test_session") == {}
