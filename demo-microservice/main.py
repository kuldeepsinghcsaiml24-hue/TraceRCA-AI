
from datetime import datetime, timezone
from uuid import uuid4
import asyncio
import os
import time

import httpx
from fastapi import FastAPI, HTTPException

app = FastAPI(title="TraceRCA Demo Payment Service")

TRACERCA_URL = os.getenv(
    "TRACERCA_URL",
    "http://127.0.0.1:8000",
)


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()



async def send_telemetry(
    trace_id: str,
    span_id: str,
    duration_ms: float,
    status: str,
    message: str,
    parent_span_id: str | None = None,
    service_name: str = "demo-payment-service",
    operation_name: str = "process-payment",
) -> None:
    now = timestamp()

    trace_payload = {
        "trace_id": trace_id,
        "span_id": span_id,
        "parent_span_id": parent_span_id,
        "service_name": service_name,
        "operation_name": operation_name,
        "timestamp": now,
        "duration_ms": duration_ms,
        "status": status,
        "attributes": {
            "demo": True,
            "http.status_code": 500 if status == "ERROR" else 200,
        },
    }

    log_payload = {
        "timestamp": now,
        "service_name": service_name,
        "message": message,
        "trace_id": trace_id,
        "span_id": span_id,
        "attributes": {"demo": True},
    }

    metric_payload = {
        "timestamp": now,
        "service_name": service_name,
        "metric_name": "demo_payment_duration_ms",
        "metric_value": duration_ms,
        "attributes": {"demo": True},
    }

    async with httpx.AsyncClient(timeout=5.0) as client:
        results = await asyncio.gather(
            client.post(
                f"{TRACERCA_URL}/telemetry/traces",
                json=trace_payload,
            ),
            client.post(
                f"{TRACERCA_URL}/telemetry/logs",
                json=log_payload,
            ),
            client.post(
                f"{TRACERCA_URL}/telemetry/metrics",
                json=metric_payload,
            ),
            return_exceptions=True,
        )

    failures = [
        str(result)
        for result in results
        if isinstance(result, Exception)
        or (hasattr(result, "is_success") and not result.is_success)
    ]

    if failures:
        raise RuntimeError(
            "Telemetry submission failed: " + "; ".join(failures)
        )

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "demo-payment-service"}



@app.get("/payment")
async def payment(fail: bool = False):
    trace_id = uuid4().hex
    gateway_span_id = uuid4().hex[:16]
    payment_span_id = uuid4().hex[:16]

    try:
        # Simulate the gateway and payment service work.
        gateway_started = time.perf_counter()
        await asyncio.sleep(0.05)
        gateway_duration_ms = (
            time.perf_counter() - gateway_started
        ) * 1000

        payment_started = time.perf_counter()
        await asyncio.sleep(0.1)
        payment_duration_ms = (
            time.perf_counter() - payment_started
        ) * 1000

        status = "ERROR" if fail else "OK"
        message = (
            "Demo payment failed intentionally"
            if fail
            else "Demo payment processed successfully"
        )

        # Parent span: api-gateway.
        await send_telemetry(
            trace_id=trace_id,
            span_id=gateway_span_id,
            duration_ms=gateway_duration_ms + payment_duration_ms,
            status=status,
            message=f"Gateway handled payment: {message}",
            parent_span_id=None,
            service_name="api-gateway",
            operation_name="handle-payment",
        )

        # Child span: demo-payment-service.
        await send_telemetry(
            trace_id=trace_id,
            span_id=payment_span_id,
            duration_ms=payment_duration_ms,
            status=status,
            message=message,
            parent_span_id=gateway_span_id,
            service_name="demo-payment-service",
            operation_name="process-payment",
        )

    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Payment demo ran, but telemetry submission failed: {exc}",
        ) from exc

    if fail:
        raise HTTPException(
            status_code=500,
            detail={
                "message": message,
                "trace_id": trace_id,
            },
        )

    return {
        "status": "success",
        "service": "demo-payment-service",
        "trace_id": trace_id,
        "duration_ms": round(payment_duration_ms, 2),
        "telemetry_submitted": True,
        "spans_submitted": 2,
    }

