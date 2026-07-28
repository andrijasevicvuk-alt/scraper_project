-- The source-neutral orchestration layer has exactly one immutable queue-owner registration.
CREATE TRIGGER IF NOT EXISTS runtime_queue_owner_singleton_insert
BEFORE INSERT ON runtime_queue_owner
WHEN EXISTS (SELECT 1 FROM runtime_queue_owner)
BEGIN
    SELECT RAISE(ABORT, 'only one authoritative queue owner may be registered');
END;

CREATE TRIGGER IF NOT EXISTS runtime_queue_owner_immutable_update
BEFORE UPDATE ON runtime_queue_owner
BEGIN
    SELECT RAISE(ABORT, 'queue owner registration is immutable');
END;

CREATE TRIGGER IF NOT EXISTS runtime_queue_owner_immutable_delete
BEFORE DELETE ON runtime_queue_owner
BEGIN
    SELECT RAISE(ABORT, 'queue owner registration is immutable');
END;
