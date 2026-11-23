import json
from datetime import datetime, timezone
from uuid import UUID

from ..cache.dependencies import redis_client
from .rca_job_schemas import RCAJobPayload


RCA_JOB_STREAM = "tracerca:rca:jobs"
RCA_JOB_GROUP = "tracerca-rca-workers"
RCA_JOB_STATE_PREFIX = "tracerca:rca:job:"
RCA_JOB_TTL_SECONDS = 7 * 24 * 60 * 60

# Worker recovery and retry policy.
RCA_JOB_MAX_ATTEMPTS = 3
RCA_JOB_RECLAIM_IDLE_MS = 60_000
RCA_JOB_BLOCK_MS = 5_000
RCA_JOB_BATCH_SIZE = 5

_VALID_STATUSES = {"QUEUED", "RUNNING", "COMPLETED", "FAILED"}

_ENQUEUE_SCRIPT = """
if redis.call('EXISTS', KEYS[1]) == 1 then
    return false
end

local message_id = redis.call(
    'XADD', KEYS[2], '*',
    'job_id', ARGV[1],
    'payload', ARGV[2]
)
redis.call('SET', KEYS[1], ARGV[3], 'EX', ARGV[4])
return message_id
"""

_UPDATE_STATE_SCRIPT = """
local raw_state = redis.call('GET', KEYS[1])
if not raw_state then
    return 0
end

local state = cjson.decode(raw_state)
local current_status = state.status
local new_status = ARGV[1]

if ARGV[4] ~= '' and current_status ~= ARGV[4] then
    return -2
end

local allowed = false
if current_status == 'QUEUED' and
   (new_status == 'RUNNING' or new_status == 'FAILED') then
    allowed = true
elseif current_status == 'RUNNING' and
       (new_status == 'QUEUED' or new_status == 'COMPLETED' or new_status == 'FAILED') then
    allowed = true
end

if not allowed then
    return -1
end

state.status = new_status
state.updated_at = ARGV[5]
state.result = cjson.null
state.result_json = ARGV[2]
state.error = cjson.decode(ARGV[3])

redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[6])
return 1
"""



_CLAIM_JOB_SCRIPT = """
local raw_state = redis.call('GET', KEYS[1])
if not raw_state then
    return {0, ''}
end

local state = cjson.decode(raw_state)
local status = state.status
local allow_reclaim = ARGV[4] == '1'

if status ~= 'QUEUED' and not (status == 'RUNNING' and allow_reclaim) then
    return {-1, ''}
end

local attempts = tonumber(state.attempt_count or 0)
local max_attempts = tonumber(ARGV[3])

if attempts >= max_attempts then
    state.status = 'FAILED'
    state.owner_token = cjson.null
    state.error = 'Maximum worker attempts exceeded.'
    state.updated_at = ARGV[2]
    redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[5])
    return {2, cjson.encode(state)}
end

state.status = 'RUNNING'
state.attempt_count = attempts + 1
state.owner_token = ARGV[1]
state.updated_at = ARGV[2]
state.error = cjson.null
state.result = cjson.null
state.result_json = nil

redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[5])
return {1, cjson.encode(state)}
"""

_UPDATE_OWNED_STATE_SCRIPT = """
local raw_state = redis.call('GET', KEYS[1])
if not raw_state then
    return 0
end

local state = cjson.decode(raw_state)
if state.status ~= 'RUNNING' or state.owner_token ~= ARGV[4] then
    return -2
end

local new_status = ARGV[1]
if new_status ~= 'COMPLETED' and new_status ~= 'FAILED' then
    return -1
end

state.status = new_status
state.updated_at = ARGV[5]
state.result = cjson.null
state.result_json = ARGV[2]
state.error = cjson.decode(ARGV[3])
state.owner_token = cjson.null

redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[6])
return 1
"""

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_key(job_id: UUID | str) -> str:
    return f"{RCA_JOB_STATE_PREFIX}{job_id}"


async def enqueue_job(payload: RCAJobPayload) -> str:
    """Atomically create the job state and publish its stream message."""
    job_id = str(payload.job_id)
    now = _utc_now()

    state = {
        "job_id": job_id,
        "incident_id": str(payload.incident.incident_id),
        "status": "QUEUED",
        "attempt_count": 0,
        "owner_token": None,
        "created_at": now,
        "updated_at": now,
        "result": None,
        "error": None,
    }

    message_id = await redis_client.client.eval(
        _ENQUEUE_SCRIPT,
        2,
        _state_key(job_id),
        RCA_JOB_STREAM,
        job_id,
        payload.model_dump_json(),
        json.dumps(state),
        RCA_JOB_TTL_SECONDS,
    )

    if message_id is None:
        raise ValueError(f"RCA job ID already exists: {job_id}")

    if isinstance(message_id, bytes):
        return message_id.decode("utf-8")
    return str(message_id)


async def get_job_state(job_id: UUID | str) -> dict | None:
    """Return the stored lifecycle state, or None for an unknown/expired job."""
    raw_state = await redis_client.client.get(_state_key(job_id))
    if raw_state is None:
        return None
    state = json.loads(raw_state)
    result_json = state.pop("result_json", None)
    if result_json is not None:
        state["result"] = json.loads(result_json)
    return state


async def update_job_state(
    job_id: UUID | str,
    *,
    status: str,
    result: dict | None = None,
    error: str | None = None,
    expected_status: str | None = None,
) -> bool:
    """Atomically validate and update a job state; return False if it is missing."""
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid RCA job status: {status}")

    if expected_status is not None and expected_status not in _VALID_STATUSES:
        raise ValueError(f"Invalid expected RCA job status: {expected_status}")

    outcome = await redis_client.client.eval(
        _UPDATE_STATE_SCRIPT,
        1,
        _state_key(job_id),
        status,
        json.dumps(result),
        json.dumps(error),
        expected_status or "",
        _utc_now(),
        RCA_JOB_TTL_SECONDS,
    )

    if outcome == 1:
        return True
    if outcome == 0:
        return False
    if outcome == -2:
        raise ValueError("RCA job status changed before the update could be applied.")
    if outcome == -1:
        raise ValueError(f"Invalid RCA job transition to {status}.")
    raise RuntimeError(f"Unexpected Redis job-state update result: {outcome}")


async def claim_job(
    job_id: UUID | str,
    *,
    owner_token: str,
    allow_reclaim: bool = False,
) -> dict | None:
    """Atomically claim a queued job or reclaim an abandoned running job.

    Returns the claimed state, a FAILED state when attempts are exhausted,
    or None when the job is missing or not eligible for this claim.
    """
    if not owner_token or not owner_token.strip():
        raise ValueError("Worker ownership token must not be empty.")

    outcome = await redis_client.client.eval(
        _CLAIM_JOB_SCRIPT,
        1,
        _state_key(job_id),
        owner_token,
        _utc_now(),
        RCA_JOB_MAX_ATTEMPTS,
        "1" if allow_reclaim else "0",
        RCA_JOB_TTL_SECONDS,
    )

    code = int(outcome[0])
    raw_state = outcome[1]

    if code == 0 or code == -1:
        return None
    if code in (1, 2):
        if isinstance(raw_state, bytes):
            raw_state = raw_state.decode("utf-8")
        state = json.loads(raw_state)
        return state
    raise RuntimeError(f"Unexpected Redis job-claim result: {code}")


async def update_owned_job_state(
    job_id: UUID | str,
    *,
    owner_token: str,
    status: str,
    result: dict | None = None,
    error: str | None = None,
) -> bool:
    """Complete or fail a job only if the caller still owns it."""
    if status not in {"COMPLETED", "FAILED"}:
        raise ValueError("Owned worker updates must use COMPLETED or FAILED.")
    if not owner_token or not owner_token.strip():
        raise ValueError("Worker ownership token must not be empty.")

    outcome = await redis_client.client.eval(
        _UPDATE_OWNED_STATE_SCRIPT,
        1,
        _state_key(job_id),
        status,
        json.dumps(result),
        json.dumps(error),
        owner_token,
        _utc_now(),
        RCA_JOB_TTL_SECONDS,
    )

    if outcome == 1:
        return True
    if outcome == 0:
        return False
    if outcome == -2:
        raise ValueError("Worker no longer owns this running job.")
    if outcome == -1:
        raise ValueError("Invalid terminal job status.")
    raise RuntimeError(f"Unexpected Redis owned-state update result: {outcome}")


async def retry_or_fail_owned_job(
    job_id: UUID | str,
    *,
    owner_token: str,
    payload_json: str,
    message_id: str,
    error: str,
) -> dict:
    """Atomically retry a failed attempt or mark the job terminal.

    The current stream message is acknowledged only in the same Redis script
    that publishes its retry or records the terminal FAILED state.
    """
    if not owner_token or not owner_token.strip():
        raise ValueError("Worker ownership token must not be empty.")
    if not message_id or not message_id.strip():
        raise ValueError("Stream message ID must not be empty.")

    outcome = await redis_client.client.eval(
        _RETRY_OWNED_JOB_SCRIPT,
        2,
        _state_key(job_id),
        RCA_JOB_STREAM,
        owner_token,
        json.dumps(error),
        _utc_now(),
        RCA_JOB_TTL_SECONDS,
        RCA_JOB_MAX_ATTEMPTS,
        payload_json,
        RCA_JOB_GROUP,
        message_id,
    )

    code = int(outcome[0])
    new_message_id = outcome[1]

    if isinstance(new_message_id, bytes):
        new_message_id = new_message_id.decode("utf-8")

    if code == 0:
        return {"status": "MISSING"}
    if code == -2:
        raise ValueError("Worker no longer owns this running job.")
    if code == 1:
        return {"status": "QUEUED", "message_id": new_message_id}
    if code == 2:
        return {"status": "FAILED", "message_id": None}

    raise RuntimeError(f"Unexpected Redis retry result: {code}")


async def reclaim_abandoned_messages(
    consumer_name: str,
    *,
    start_id: str = "0-0",
    min_idle_ms: int = RCA_JOB_RECLAIM_IDLE_MS,
    count: int = RCA_JOB_BATCH_SIZE,
) -> tuple[str, list]:
    """Transfer sufficiently idle pending messages to this recovery consumer.

    Returns the next Redis scan cursor and the claimed stream messages.
    Continue from the returned cursor until Redis returns ``0-0``.
    """
    if not consumer_name or not consumer_name.strip():
        raise ValueError("Consumer name must not be empty.")
    if min_idle_ms < 0:
        raise ValueError("Minimum idle time cannot be negative.")
    if count < 1:
        raise ValueError("Claim batch size must be at least one.")

    response = await redis_client.client.xautoclaim(
        RCA_JOB_STREAM,
        RCA_JOB_GROUP,
        consumer_name,
        min_idle_ms,
        start_id,
        count=count,
    )

    if not response or len(response) < 2:
        raise RuntimeError("Unexpected Redis XAUTOCLAIM response.")

    next_cursor = response[0]
    messages = response[1]

    if isinstance(next_cursor, bytes):
        next_cursor = next_cursor.decode("utf-8")

    return str(next_cursor), messages


async def acknowledge_job_message(message_id: str) -> int:
    """Acknowledge a handled stream message in the RCA consumer group."""
    if not message_id or not message_id.strip():
        raise ValueError("Stream message ID must not be empty.")

    acknowledged = await redis_client.client.xack(
        RCA_JOB_STREAM,
        RCA_JOB_GROUP,
        message_id,
    )
    return int(acknowledged)


_RETRY_OWNED_JOB_SCRIPT = """
local raw_state = redis.call('GET', KEYS[1])
if not raw_state then
    return {0, ''}
end

local state = cjson.decode(raw_state)
if state.status ~= 'RUNNING' or state.owner_token ~= ARGV[1] then
    return {-2, ''}
end

local attempts = tonumber(state.attempt_count or 0)
local max_attempts = tonumber(ARGV[5])
local error_value = cjson.decode(ARGV[2])

state.updated_at = ARGV[3]
state.error = error_value
state.result = cjson.null
state.owner_token = cjson.null

if attempts < max_attempts then
    state.status = 'QUEUED'
    local new_message_id = redis.call(
        'XADD', KEYS[2], '*',
        'job_id', state.job_id,
        'payload', ARGV[6]
    )
    redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[4])
    redis.call('XACK', KEYS[2], ARGV[7], ARGV[8])
    return {1, new_message_id}
end

state.status = 'FAILED'
redis.call('SET', KEYS[1], cjson.encode(state), 'EX', ARGV[4])
redis.call('XACK', KEYS[2], ARGV[7], ARGV[8])
return {2, ''}
"""


async def ensure_consumer_group() -> None:
    """Create the Redis Streams consumer group if it does not exist."""
    try:
        await redis_client.client.xgroup_create(
            RCA_JOB_STREAM,
            RCA_JOB_GROUP,
            id="0",
            mkstream=True,
        )
    except Exception as exc:
        # Redis BUSYGROUP means another process already created the group.
        if "BUSYGROUP" not in str(exc):
            raise
