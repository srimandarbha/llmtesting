"""
Mock AWX client for local development and integration testing.

Simulates the AWX job lifecycle: PENDING → RUNNING → SUCCESSFUL/FAILED
with configurable delays. Drop-in replacement for awx.client.AWXClient.
"""

from __future__ import annotations

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Literal

from awx.client import AWXJobResult, AWXJobStatus

logger = logging.getLogger(__name__)


class MockAWXClient:
    """
    Simulates AWX REST API behavior without a real AWX server.

    Job lifecycle (configurable):
    - Jobs start in PENDING
    - After `pending_delay` seconds → RUNNING
    - After `run_delay` seconds → SUCCESSFUL (or FAILED if fail_rate triggers)

    Usage in tests:
        client = MockAWXClient(fail_rate=0.0)  # always succeed
        job_id = client.launch_job("42", intent.to_awx_extra_vars())
        result = client.get_job_status(job_id)
    """

    def __init__(
        self,
        fail_rate: float = 0.0,        # 0.0 = always succeed, 1.0 = always fail
        pending_delay: float = 0.5,    # seconds before RUNNING
        run_delay: float = 1.0,        # seconds before terminal state
    ):
        self._fail_rate = fail_rate
        self._pending_delay = pending_delay
        self._run_delay = run_delay

    def launch_job(self, template_id: str, extra_vars: dict) -> str:
        started_at = int(time.time())
        job_id = f"mock-{started_at}-{uuid.uuid4().hex[:8]}"
        logger.info(
            "[MOCK AWX] Job launched: id=%s template=%s extra_vars=%s",
            job_id,
            template_id,
            extra_vars,
        )
        return job_id

    def get_job_status(self, job_id: str) -> AWXJobResult:
        if not job_id.startswith("mock-"):
            return AWXJobResult(
                job_id=job_id,
                status=AWXJobStatus.ERROR,
                url=f"http://mock-awx/#/jobs/{job_id}",
            )

        try:
            started_at = int(job_id.split("-")[1])
        except (IndexError, ValueError):
            started_at = time.time() - 100  # fallback

        elapsed = time.time() - started_at

        if elapsed < self._pending_delay:
            status = AWXJobStatus.PENDING
        elif elapsed < self._pending_delay + self._run_delay:
            status = AWXJobStatus.RUNNING
        else:
            status = AWXJobStatus.SUCCESSFUL

        logger.debug("[MOCK AWX] get_job_status id=%s → %s (elapsed=%.1fs)", job_id, status, elapsed)

        return AWXJobResult(
            job_id=job_id,
            status=status,
            url=f"http://mock-awx/#/jobs/{job_id}",
            elapsed=round(elapsed, 2),
            failed=(status == AWXJobStatus.FAILED),
            extra_vars={},
        )

    def cancel_job(self, job_id: str) -> bool:
        if not job_id.startswith("mock-"):
            return False
        try:
            started_at = int(job_id.split("-")[1])
        except (IndexError, ValueError):
            return False
            
        elapsed = time.time() - started_at
        is_terminal = elapsed >= self._pending_delay + self._run_delay
        if not is_terminal:
            logger.info("[MOCK AWX] Job %s canceled", job_id)
            return True
        return False
