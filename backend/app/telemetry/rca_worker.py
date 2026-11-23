"""Background worker for asynchronous TraceRCA RCA jobs."""

import asyncio
import logging
from uuid import UUID, uuid4

from ..cache.dependencies import redis_client
from ..db.database import AsyncSessionLocal
from ..db.neo4j import neo4j_connection
from .rca_execution_service import execute_rca_analysis
from .rca_job_queue import (
    RCA_JOB_BATCH_SIZE,
    RCA_JOB_BLOCK_MS,
    RCA_JOB_GROUP,
    RCA_JOB_MAX_ATTEMPTS,
    RCA_JOB_RECLAIM_IDLE_MS,
    RCA_JOB_STREAM,
    acknowledge_job_message,
    claim_job,
    ensure_consumer_group,
    get_job_state,
    reclaim_abandoned_messages,
    retry_or_fail_owned_job,
    update_owned_job_state,
)
from .rca_job_schemas import RCAJobPayload


logger = logging.getLogger("tracerca.rca_worker")
HEARTBEAT_INTERVAL_SECONDS = max(
    1,
    RCA_JOB_RECLAIM_IDLE_MS // 3000,
)

# Refresh the pending-message idle time only while this worker still owns
# the RUNNING job. The ownership check and XCLAIM happen atomically in Redis.
_HEARTBEAT_SCRIPT = """
local raw_state = redis.call('GET', KEYS[1])
if not raw_state then
    return 0
end

local state = cjson.decode(raw_state)
if state.status ~= 'RUNNING' or state.owner_token ~= ARGV[4] then
    return 0
end

local claimed = redis.call(
    'XCLAIM', KEYS[2], ARGV[1], ARGV[2], 0, ARGV[3], 'JUSTID'
)
if #claimed == 0 then
    return 0
end

return 1
"""


class RCAWorker:
    """Consume RCA jobs using Redis Streams and execute the RCA pipeline."""

    def __init__(self) -> None:
        self.consumer_name = f"rca-worker-{uuid4()}"
        self.reclaim_cursor = "0-0"

    async def run(self) -> None:
        """Continuously recover abandoned messages and consume new jobs."""
        await ensure_consumer_group()
        logger.info("RCA worker started: %s", self.consumer_name)

        while True:
            try:
                self.reclaim_cursor, abandoned = (
                    await reclaim_abandoned_messages(
                        self.consumer_name,
                        start_id=self.reclaim_cursor,
                        min_idle_ms=RCA_JOB_RECLAIM_IDLE_MS,
                        count=RCA_JOB_BATCH_SIZE,
                    )
                )

                if abandoned:
                    for message_id, fields in abandoned:
                        await self._process_message(
                            str(message_id), fields, allow_reclaim=True
                        )
                    continue

                response = await redis_client.client.xreadgroup(
                    groupname=RCA_JOB_GROUP,
                    consumername=self.consumer_name,
                    streams={RCA_JOB_STREAM: ">"},
                    count=RCA_JOB_BATCH_SIZE,
                    block=RCA_JOB_BLOCK_MS,
                )

                for _, messages in response or []:
                    for message_id, fields in messages:
                        await self._process_message(
                            str(message_id), fields, allow_reclaim=False
                        )

            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Worker loop error; will retry.")
                await asyncio.sleep(1)

    async def _heartbeat(
        self,
        job_id: UUID,
        message_id: str,
        owner_token: str,
        ownership_lost: asyncio.Event,
    ) -> None:
        """Keep a live job's pending message from being reclaimed."""
        state_key = f"tracerca:rca:job:{job_id}"

        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)

            try:
                refreshed = await redis_client.client.eval(
                    _HEARTBEAT_SCRIPT,
                    2,
                    state_key,
                    RCA_JOB_STREAM,
                    RCA_JOB_GROUP,
                    self.consumer_name,
                    message_id,
                    owner_token,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "Heartbeat failed for RCA job %s", job_id
                )
                continue

            if int(refreshed) != 1:
                ownership_lost.set()
                logger.warning(
                    "Worker lost ownership of RCA job %s", job_id
                )
                return

    @staticmethod
    async def _stop_heartbeat(task: asyncio.Task) -> None:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    async def _process_message(
        self,
        message_id: str,
        fields: dict,
        *,
        allow_reclaim: bool,
    ) -> None:
        """Claim and execute one message, safely completing or retrying it."""
        raw_job_id = fields.get("job_id")
        payload_json = fields.get("payload", "{}")

        try:
            job_id = UUID(str(raw_job_id))
        except (ValueError, TypeError, AttributeError):
            logger.error("Discarding message with invalid job ID: %s", message_id)
            await acknowledge_job_message(message_id)
            return

        owner_token = str(uuid4())

        try:
            claimed_state = await claim_job(
                job_id,
                owner_token=owner_token,
                allow_reclaim=allow_reclaim,
            )
        except Exception:
            logger.exception("Could not claim RCA job %s", job_id)
            return

        if claimed_state is None:
            # A terminal duplicate can be acknowledged. Do not acknowledge a
            # job that is still queued or owned by another worker.
            state = await get_job_state(job_id)
            if state and state.get("status") in {"COMPLETED", "FAILED"}:
                await acknowledge_job_message(message_id)
            return

        if claimed_state.get("status") == "FAILED":
            await acknowledge_job_message(message_id)
            return

        if (
            claimed_state.get("status") != "RUNNING"
            or claimed_state.get("owner_token") != owner_token
        ):
            return

        try:
            payload = RCAJobPayload.model_validate_json(payload_json)
            if payload.job_id != job_id:
                raise ValueError("Payload job ID does not match stream message.")
        except Exception:
            logger.warning("Invalid RCA payload for job %s", job_id)
            try:
                updated = await update_owned_job_state(
                    job_id,
                    owner_token=owner_token,
                    status="FAILED",
                    error="Invalid RCA job payload.",
                )
                if updated:
                    await acknowledge_job_message(message_id)
            except Exception:
                logger.exception("Could not finalize invalid job %s", job_id)
            return

        ownership_lost = asyncio.Event()
        heartbeat_task = asyncio.create_task(
            self._heartbeat(
                job_id, message_id, owner_token, ownership_lost
            )
        )

        try:
            async with AsyncSessionLocal() as db:
                result = await execute_rca_analysis(
                    db=db,
                    incident=payload.incident,
                )

            result_data = result.model_dump(mode="json")

        except asyncio.CancelledError:
            await self._stop_heartbeat(heartbeat_task)
            raise
        except Exception:
            logger.exception("RCA analysis failed for job %s", job_id)
            await self._stop_heartbeat(heartbeat_task)

            if ownership_lost.is_set():
                return

            try:
                outcome = await retry_or_fail_owned_job(
                    job_id,
                    owner_token=owner_token,
                    payload_json=payload_json,
                    message_id=message_id,
                    error="RCA analysis failed. Check worker logs for details.",
                )
                logger.info(
                    "RCA job %s attempt outcome: %s",
                    job_id,
                    outcome.get("status"),
                )
            except Exception:
                logger.exception(
                    "Could not record failure or schedule retry for %s",
                    job_id,
                )
            return

        await self._stop_heartbeat(heartbeat_task)

        if ownership_lost.is_set():
            logger.warning(
                "Skipping completion update for job %s after ownership loss",
                job_id,
            )
            return

        try:
            updated = await update_owned_job_state(
                job_id,
                owner_token=owner_token,
                status="COMPLETED",
                result=result_data,
            )

            if updated:
                await acknowledge_job_message(message_id)
                logger.info("RCA job completed: %s", job_id)
            else:
                logger.warning(
                    "Job state expired before completion: %s", job_id
                )
                await acknowledge_job_message(message_id)

        except Exception:
            # If completion was saved but acknowledgement failed, recovery
            # will see the terminal state and acknowledge the old message.
            logger.exception("Could not finalize RCA job %s", job_id)


async def main() -> None:
    """Start the standalone worker process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    await redis_client.connect()
    try:
        await neo4j_connection.connect()
        try:
            worker = RCAWorker()
            await worker.run()
        finally:
            await neo4j_connection.close()
    finally:
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())


