"""Persistent local analysis jobs, reports and alert state."""

from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class VideoHistory:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS video_jobs (
                    id TEXT PRIMARY KEY, filename TEXT NOT NULL, size INTEGER,
                    camera TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
                    status TEXT NOT NULL, result_key TEXT, error TEXT
                );
                CREATE TABLE IF NOT EXISTS video_alert_status (
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    event_id TEXT NOT NULL, status TEXT NOT NULL,
                    PRIMARY KEY(job_id, event_id)
                );
                CREATE TABLE IF NOT EXISTS video_job_metrics (
                    job_id TEXT PRIMARY KEY REFERENCES video_jobs(id),
                    metrics TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS pending_replays (
                    job_id TEXT PRIMARY KEY REFERENCES video_jobs(id)
                );
                CREATE TABLE IF NOT EXISTS video_job_sources (
                    job_id TEXT PRIMARY KEY REFERENCES video_jobs(id),
                    upload_key TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS video_results (
                    result_key TEXT PRIMARY KEY, report TEXT NOT NULL
                );
            """)
            columns = {row["name"] for row in db.execute("PRAGMA table_info(video_jobs)")}
            if "mode" not in columns:
                db.execute("ALTER TABLE video_jobs ADD COLUMN mode TEXT")
            # Completed old replays lost their pending marker when published.
            # Once Live was in use, an unmarked row cannot safely be classified.
            first_live = db.execute("""SELECT min(started_at) FROM video_jobs
                WHERE mode IN ('demo','camera') OR (size=0 AND camera<>'Unassigned')
                   OR id IN (SELECT job_id FROM pending_replays)""").fetchone()[0]
            db.execute("""UPDATE video_jobs SET mode=CASE
                          WHEN size=0 AND camera<>'Unassigned' THEN 'camera'
                          WHEN id IN (SELECT job_id FROM pending_replays) THEN 'demo'
                          WHEN started_at>=? THEN 'legacy'
                          ELSE 'offline' END WHERE mode IS NULL""", (first_live,))
            db.execute("""UPDATE video_jobs SET status='Failed', finished_at=?,
                          error='The analysis service restarted before the job completed'
                          WHERE status='Processing'""", (now(),))
            db.execute("""DELETE FROM pending_replays WHERE job_id IN
                          (SELECT id FROM video_jobs WHERE status='Failed')""")

    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def start(self, filename, size, camera, *, pending_replay=False, upload_key=None, mode=None):
        identifier = uuid4().hex
        with closing(self.connect()) as db, db:
            db.execute("""INSERT INTO video_jobs (id,filename,size,camera,started_at,status,mode)
                          VALUES (?,?,?,?,?,'Processing',?)""",
                       (identifier, filename, size, camera, now(), mode or ("demo" if pending_replay else "offline")))
            if pending_replay:
                db.execute("INSERT INTO pending_replays(job_id) VALUES(?)", (identifier,))
            if upload_key:
                db.execute("INSERT INTO video_job_sources(job_id,upload_key) VALUES(?,?)", (identifier, upload_key))
        return identifier

    def finish(self, identifier, result_key, problem, result=None):
        status = "Completed" if result_key else "Cancelled" if problem == "stopped" else "Failed"
        with closing(self.connect()) as db, db:
            db.execute("""UPDATE video_jobs SET finished_at=?, status=?, result_key=?, error=?
                          WHERE id=?""", (now(), status, result_key, problem, identifier))
            if result and result.get("traffic"):
                self.write_metrics(db, identifier, result)
            if result_key and result is not None:
                self.write_report(db, result_key, result)
            if status != "Completed":
                db.execute("DELETE FROM pending_replays WHERE job_id=?", (identifier,))

    def reveal_replay(self, identifier):
        with closing(self.connect()) as db, db:
            job = db.execute("SELECT result_key FROM video_jobs WHERE id=? AND status='Completed'", (identifier,)).fetchone()
            if job is None:
                return False
            db.execute("DELETE FROM pending_replays WHERE job_id=?", (identifier,))
            return True

    @staticmethod
    def write_metrics(db, identifier, result):
        traffic = result["traffic"]
        metrics = {"crossings": len(traffic["crossings"]), "average_visible": traffic["average_visible"],
                   "peak": max(w["visible"] for w in traffic["windows"]), "alerts": len(traffic["alerts"])}
        latest = traffic["windows"][-1]
        phases = (traffic.get("signal_schedule") or {}).get("phases", [])
        metrics.update(density=latest.get("level"), green=latest.get("green", {}),
                       next_phase={k: phases[0][k] for k in ("phase", "green_s")
                                   if k in phases[0]} if phases else None)
        db.execute("INSERT OR REPLACE INTO video_job_metrics(job_id, metrics) VALUES(?,?)",
                   (identifier, json.dumps(metrics)))

    @staticmethod
    def write_report(db, key, result):
        db.execute("INSERT OR IGNORE INTO video_results VALUES (?,?)",
                   (key, json.dumps(result, separators=(",", ":"))))

    def migrate_reports(self, read_report):
        """Import pre-existing report files without changing their analysis IDs."""
        with closing(self.connect()) as db, db:
            rows = db.execute("""SELECT id,result_key,metrics FROM video_jobs
                LEFT JOIN video_job_metrics ON id=job_id WHERE status='Completed' AND result_key IS NOT NULL
                AND (result_key NOT IN (SELECT result_key FROM video_results)
                     OR metrics IS NULL OR json_extract(metrics, '$.density') IS NULL)""").fetchall()
            for row in rows:
                result = read_report(row["result_key"])
                if result is None:
                    continue
                self.write_report(db, row["result_key"], result)
                if result.get("traffic"):
                    self.write_metrics(db, row["id"], result)

    def report(self, key):
        with closing(self.connect()) as db:
            row = db.execute("SELECT report FROM video_results WHERE result_key=?", (key,)).fetchone()
            return row["report"] if row else None

    def delete_offline(self, identifier, remove_report, *, extra_key=None):
        """Delete offline rows and remove caches only when no other job uses them."""
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            condition = "mode='offline'" + (" AND id=?" if identifier is not None else "")
            params = (identifier,) if identifier is not None else ()
            rows = db.execute(f"SELECT id,result_key FROM video_jobs WHERE {condition}", params).fetchall()
            if identifier is not None and not rows:
                return 0
            keys = {row["result_key"] for row in rows if row["result_key"]}
            if extra_key:
                keys.add(extra_key)
            for table in ("video_alert_status", "video_job_metrics", "pending_replays", "video_job_sources"):
                db.execute(f"DELETE FROM {table} WHERE job_id IN (SELECT id FROM video_jobs WHERE {condition})", params)
            db.execute(f"DELETE FROM video_jobs WHERE {condition}", params)
            for key in keys:
                if not db.execute("SELECT 1 FROM video_jobs WHERE result_key=? LIMIT 1", (key,)).fetchone():
                    remove_report(key)
                    db.execute("DELETE FROM video_results WHERE result_key=?", (key,))
            return len(rows)

    def recent(self):
        with closing(self.connect()) as db:
            rows = db.execute("""SELECT video_jobs.*, video_job_metrics.metrics,
                                        video_job_sources.job_id IS NOT NULL AS has_video FROM video_jobs
                                 LEFT JOIN video_job_metrics ON video_jobs.id=video_job_metrics.job_id
                                 LEFT JOIN video_job_sources ON video_jobs.id=video_job_sources.job_id
                                 WHERE NOT EXISTS (SELECT 1 FROM pending_replays WHERE job_id=video_jobs.id)
                                 ORDER BY video_jobs.rowid DESC""")
            return [{**row, "metrics": json.loads(row["metrics"]) if row["metrics"] else None} for row in rows]

    def source(self, identifier):
        with closing(self.connect()) as db:
            return db.execute("""SELECT filename,size,upload_key FROM video_jobs
                                 JOIN video_job_sources ON job_id=id
                                 WHERE id=? AND status='Completed'
                                   AND NOT EXISTS (SELECT 1 FROM pending_replays WHERE job_id=video_jobs.id)""",
                              (identifier,)).fetchone()

    def statuses(self, identifier):
        with closing(self.connect()) as db:
            return {row["event_id"]: row["status"] for row in db.execute(
                "SELECT event_id,status FROM video_alert_status WHERE job_id=?", (identifier,))}

    def set_status(self, identifier, event, status):
        with closing(self.connect()) as db, db:
            return db.execute("""INSERT INTO video_alert_status(job_id,event_id,status)
                                 SELECT id,?,? FROM video_jobs WHERE id=?
                                 ON CONFLICT(job_id,event_id) DO UPDATE SET status=excluded.status""",
                              (event, status, identifier)).rowcount > 0
