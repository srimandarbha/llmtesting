"""
AWX REST API client.

Design rules (NON-NEGOTIABLE):
- AWX is the ONLY way Ansible playbooks are executed. No subprocess.
- extra_vars ALWAYS comes from a validated RemediationIntent Pydantic model.
- This client never constructs extra_vars from raw strings or raw LLM output.

AWX API reference:
  POST /api/v2/job_templates/{id}/launch/  → launch job
  GET  /api/v2/jobs/{id}/                  → get job status
  POST /api/v2/jobs/{id}/cancel/           → cancel job
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from agents.config import AWX_API_TOKEN, AWX_BASE_URL

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AWX job status enum
# ---------------------------------------------------------------------------


class AWXJobStatus(str, Enum):
    PENDING = "pending"
    WAITING = "waiting"
    RUNNING = "running"
    SUCCESSFUL = "successful"
    FAILED = "failed"
    ERROR = "error"
    CANCELED = "canceled"

    @property
    def is_terminal(self) -> bool:
        return self in (
            AWXJobStatus.SUCCESSFUL,
            AWXJobStatus.FAILED,
            AWXJobStatus.ERROR,
            AWXJobStatus.CANCELED,
        )

    @property
    def is_success(self) -> bool:
        return self == AWXJobStatus.SUCCESSFUL


@dataclass
class AWXJobResult:
    job_id: str
    status: AWXJobStatus
    url: str
    elapsed: float | None = None
    failed: bool = False
    extra_vars: dict | None = None


# ---------------------------------------------------------------------------
# Real AWX REST client
# ---------------------------------------------------------------------------


class AWXClient:
    """
    Synchronous AWX REST API client using httpx.

    Usage:
        client = AWXClient()
        job_id = client.launch_job(template_id="42", extra_vars=intent.to_awx_extra_vars())
        result = client.get_job_status(job_id)
    """

    def __init__(
        self,
        base_url: str = AWX_BASE_URL,
        api_token: str = AWX_API_TOKEN,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self._headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }
        self._timeout = timeout

    def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(headers=self._headers, timeout=self._timeout) as client:
                response = getattr(client, method)(url, **kwargs)
                response.raise_for_status()
                # Some AWX endpoints return 204 No Content on cancel
                return response.json() if response.content else {}
        except httpx.HTTPStatusError as e:
            logger.error("AWX HTTP error %s %s → %s", method.upper(), url, e.response.status_code)
            raise
        except httpx.RequestError as e:
            logger.error("AWX connection error %s %s → %s", method.upper(), url, e)
            raise

    def launch_job(self, template_id: str, extra_vars: dict) -> str:
        """
        Launch an AWX job template.

        Parameters
        ----------
        template_id:
            AWX job template ID (from the AWX UI / API).
        extra_vars:
            Dict produced by RemediationIntent.to_awx_extra_vars().
            NEVER pass raw strings from LLM output here.

        Returns
        -------
        AWX job ID as a string.
        """
        logger.info(
            "Launching AWX job template=%s extra_vars=%s", template_id, extra_vars
        )
        result = self._request(
            "post",
            f"/api/v2/job_templates/{template_id}/launch/",
            json={"extra_vars": extra_vars},
        )
        job_id = str(result["id"])
        logger.info("AWX job launched: job_id=%s", job_id)
        return job_id

    def get_job_status(self, job_id: str) -> AWXJobResult:
        """Poll the current status of an AWX job."""
        result = self._request("get", f"/api/v2/jobs/{job_id}/")
        status_str = result.get("status", "error")

        try:
            status = AWXJobStatus(status_str)
        except ValueError:
            status = AWXJobStatus.ERROR

        return AWXJobResult(
            job_id=job_id,
            status=status,
            url=f"{self.base_url}/#/jobs/playbook/{job_id}/details",
            elapsed=result.get("elapsed"),
            failed=result.get("failed", False),
            extra_vars=result.get("extra_vars"),
        )

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a running AWX job. Returns True if cancel was accepted."""
        try:
            self._request("post", f"/api/v2/jobs/{job_id}/cancel/")
            logger.info("AWX job %s cancel requested", job_id)
            return True
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 405:
                # 405 = already terminal
                return False
            raise


# ---------------------------------------------------------------------------
# Factory: returns real or mock client based on config
# ---------------------------------------------------------------------------


def get_awx_client() -> AWXClient:
    """
    Returns the real AWXClient.
    Import simulation.mock_client.MockAWXClient for local development.
    Use agents.config.USE_MOCK_AWX to switch automatically in worker/tasks.py.
    """
    return AWXClient()
