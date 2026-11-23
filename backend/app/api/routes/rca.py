from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.database import get_db
from ...telemetry.incident import IncidentContext
from ...telemetry.rca_api_schemas import RCAAnalysisResponse
from ...telemetry.rca_execution_service import execute_rca_analysis
from ...telemetry.rca_job_queue import enqueue_job, get_job_state
from ...telemetry.rca_job_schemas import (
    RCAJobPayload,
    RCAJobStatusResponse,
    RCAJobSubmissionResponse,
)

router = APIRouter(prefix="/rca", tags=["Root Cause Analysis"])


@router.post("/analyze", response_model=RCAAnalysisResponse)
async def analyze_root_cause(
    incident: IncidentContext,
    db: AsyncSession = Depends(get_db),
):
    """Build incident evidence and return ranked root-cause hypotheses."""
    try:
        return await execute_rca_analysis(
            db=db,
            incident=incident,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Root cause analysis failed.",
        ) from exc

@router.post("/jobs", response_model=RCAJobSubmissionResponse, status_code=202)
async def submit_rca_job(
    incident: IncidentContext,
):
    """Queue an RCA job for processing by the separate worker."""
    payload = RCAJobPayload(incident=incident)

    try:
        await enqueue_job(payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=409,
            detail="RCA job could not be queued because its ID already exists.",
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="RCA job queue is temporarily unavailable.",
        ) from exc

    job_url = f"/rca/jobs/{payload.job_id}"
    return RCAJobSubmissionResponse(
        job_id=payload.job_id,
        incident_id=incident.incident_id,
        status="QUEUED",
        status_url=job_url,
        result_url=job_url,
    )


@router.get("/jobs/{job_id}", response_model=RCAJobStatusResponse)
async def get_rca_job(
    job_id: UUID,
):
    """Return an RCA job's lifecycle state and its result when available."""
    try:
        state = await get_job_state(job_id)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="RCA job status is temporarily unavailable.",
        ) from exc

    if state is None:
        raise HTTPException(
            status_code=404,
            detail="RCA job not found or its status has expired.",
        )

    return state

