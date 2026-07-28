"""Authoritative detail-fetch queue transitions and bounded retry recovery."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from database.connection import RuntimeDatabase
from database.repositories import JobLease, _timestamp


class QueueTransitionError(RuntimeError):
    """Raised when a worker attempts a transition it does not own."""


class DetailFetchQueue:
    """The only component permitted to lease, retry, complete, or recover jobs."""

    OWNER_NAME = "source_neutral_orchestrator"

    def __init__(self, database: RuntimeDatabase) -> None:
        self.database = database
        with database.write_transaction() as connection:
            existing = connection.execute("SELECT owner_name FROM runtime_queue_owner LIMIT 1").fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO runtime_queue_owner(owner_name, registered_at) VALUES (?, ?)",
                    (self.OWNER_NAME, _timestamp()),
                )
            elif existing["owner_name"] != self.OWNER_NAME:
                raise QueueTransitionError("a different queue owner is registered")

    def lease_next(self, worker_id: str, lease_seconds: int = 60, now: datetime | None = None) -> JobLease | None:
        if lease_seconds < 1:
            raise ValueError("lease_seconds must be positive")
        current = now or datetime.now(UTC)
        expires = current + timedelta(seconds=lease_seconds)
        with self.database.write_transaction() as connection:
            row = connection.execute(
                "SELECT * FROM detail_fetch_jobs WHERE state='pending' AND scheduled_at <= ? "
                "AND attempt_count < max_attempts ORDER BY priority DESC, scheduled_at, created_at LIMIT 1",
                (_timestamp(current),),
            ).fetchone()
            if row is None:
                return None
            attempt_number = int(row["attempt_count"]) + 1
            connection.execute(
                "UPDATE detail_fetch_jobs SET state='processing', attempt_count=?, lease_owner=?, lease_expires_at=?, updated_at=? "
                "WHERE job_id=? AND state='pending'",
                (attempt_number, worker_id, _timestamp(expires), _timestamp(current), row["job_id"]),
            )
            connection.execute(
                "INSERT INTO job_attempts(job_attempt_id, job_id, attempt_number, worker_id, started_at) VALUES (?, ?, ?, ?, ?)",
                (str(uuid4()), row["job_id"], attempt_number, worker_id, _timestamp(current)),
            )
        return JobLease(
            job_id=str(row["job_id"]), source_name=str(row["source_name"]),
            source_listing_key=str(row["source_listing_key"]), reason_code=str(row["reason_code"]),
            attempt_number=attempt_number, max_attempts=int(row["max_attempts"]), lease_owner=worker_id,
            lease_expires_at=_timestamp(expires),
        )

    def succeed(self, job_id: str, worker_id: str, now: datetime | None = None) -> None:
        self._finish(job_id, worker_id, success=True, error_class=None, now=now)

    def fail(self, job_id: str, worker_id: str, error_class: str, now: datetime | None = None) -> str:
        return self._finish(job_id, worker_id, success=False, error_class=error_class, now=now)

    def _finish(self, job_id: str, worker_id: str, success: bool, error_class: str | None, now: datetime | None) -> str:
        current = now or datetime.now(UTC)
        with self.database.write_transaction() as connection:
            row = connection.execute("SELECT * FROM detail_fetch_jobs WHERE job_id=?", (job_id,)).fetchone()
            if row is None or row["state"] != "processing" or row["lease_owner"] != worker_id:
                raise QueueTransitionError("worker does not own an active lease for this job")
            if success:
                state, outcome = "succeeded", "succeeded"
            elif int(row["attempt_count"]) >= int(row["max_attempts"]):
                state, outcome = "failed_exhausted", "failed_exhausted"
            else:
                state, outcome = "pending", "failed_retryable"
            connection.execute(
                "UPDATE detail_fetch_jobs SET state=?, lease_owner=NULL, lease_expires_at=NULL, scheduled_at=?, "
                "last_error_class=?, updated_at=? WHERE job_id=?",
                (state, _timestamp(current), error_class, _timestamp(current), job_id),
            )
            connection.execute(
                "UPDATE job_attempts SET finished_at=?, outcome=?, error_class=? "
                "WHERE job_id=? AND attempt_number=?",
                (_timestamp(current), outcome, error_class, job_id, row["attempt_count"]),
            )
        return state

    def recover_abandoned(self, now: datetime | None = None) -> dict[str, int]:
        current = now or datetime.now(UTC)
        recovered = exhausted = 0
        with self.database.write_transaction() as connection:
            rows = connection.execute(
                "SELECT job_id, attempt_count, max_attempts FROM detail_fetch_jobs "
                "WHERE state='processing' AND lease_expires_at < ?",
                (_timestamp(current),),
            ).fetchall()
            for row in rows:
                state = "failed_exhausted" if int(row["attempt_count"]) >= int(row["max_attempts"]) else "pending"
                connection.execute(
                    "UPDATE detail_fetch_jobs SET state=?, lease_owner=NULL, lease_expires_at=NULL, scheduled_at=?, "
                    "last_error_class='abandoned_lease', updated_at=? WHERE job_id=?",
                    (state, _timestamp(current), _timestamp(current), row["job_id"]),
                )
                connection.execute(
                    "UPDATE job_attempts SET finished_at=?, outcome='abandoned', error_class='abandoned_lease' "
                    "WHERE job_id=? AND attempt_number=?",
                    (_timestamp(current), row["job_id"], row["attempt_count"]),
                )
                if state == "pending":
                    recovered += 1
                else:
                    exhausted += 1
        return {"recovered": recovered, "exhausted": exhausted}
