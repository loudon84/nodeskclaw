"""Build smc.client-release.v1."""

from __future__ import annotations

from typing import Any

SCHEMA = "smc.client-release.v1"

# FR-216-30: Build Success must not imply Release Certified.
BUILD_STATUS_SUCCESS = "success"
BUILD_STATUS_FAILED = "failed"
CERT_STATUS_UNCERTIFIED = "uncertified"
CERT_STATUS_CERTIFIED = "certified"
CERT_STATUS_FAILED = "failed"


def build_client_release_manifest(
    *,
    release_version: str,
    requirements: dict[str, str],
    work: dict[str, Any],
    hermes: dict[str, Any],
    opsi: dict[str, Any] | None,
    opsi_client_agent: dict[str, Any] | None,
    build_id: str,
    live_eligible: bool,
    hermes_installer: dict[str, Any] | None = None,
    build_status: str = BUILD_STATUS_SUCCESS,
    certification_status: str = CERT_STATUS_UNCERTIFIED,
    certification: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if build_status not in {BUILD_STATUS_SUCCESS, BUILD_STATUS_FAILED}:
        raise ValueError(f"invalid buildStatus: {build_status}")
    if certification_status not in {
        CERT_STATUS_UNCERTIFIED,
        CERT_STATUS_CERTIFIED,
        CERT_STATUS_FAILED,
    }:
        raise ValueError(f"invalid certificationStatus: {certification_status}")
    if certification_status == CERT_STATUS_CERTIFIED:
        evidence = certification or {}
        if not evidence.get("artifactSha256") or not evidence.get("evidenceLocator"):
            raise ValueError(
                "certificationStatus=certified requires artifactSha256 and evidenceLocator"
            )

    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "releaseVersion": release_version,
        "platform": "windows",
        "architecture": "amd64",
        "requirements": requirements,
        "work": {
            "version": work["version"],
            "sha256": work["sha256"],
            "setupSha256": work.get("setupSha256", work["sha256"]),
            "portableSha256": work.get("portableSha256", work["sha256"]),
        },
        "hermes": {
            "version": hermes["version"],
            "profile": hermes["profile"],
            "sourceRevision": hermes["sourceRevision"],
            "artifactSha256": hermes["artifactSha256"],
            "manifestSha256": hermes["manifestSha256"],
        },
        "buildId": build_id,
        "liveEligible": live_eligible,
        "buildStatus": build_status,
        "certificationStatus": certification_status,
    }
    if certification is not None:
        payload["certification"] = {
            "artifactSha256": certification.get("artifactSha256", ""),
            "runnerImageOrSnapshotId": certification.get("runnerImageOrSnapshotId", ""),
            "evidenceLocator": certification.get("evidenceLocator", ""),
            "certifiedAt": certification.get("certifiedAt", ""),
        }
    if opsi is not None:
        payload["opsi"] = {
            "productVersion": opsi["productVersion"],
            "packageVersion": opsi["packageVersion"],
            "controllerRevision": opsi["controllerRevision"],
            "artifactSha256": opsi["artifactSha256"],
        }
    if opsi_client_agent is not None:
        payload["opsiClientAgent"] = {
            "sha256": opsi_client_agent["sha256"],
            "version": opsi_client_agent.get("version", ""),
            "authenticodeStatus": opsi_client_agent.get("authenticodeStatus", ""),
        }
    if hermes_installer is not None:
        payload["hermesInstaller"] = {
            "sha256": hermes_installer["sha256"],
            "version": hermes_installer.get("version", ""),
            "authenticodeStatus": hermes_installer.get("authenticodeStatus", ""),
        }
        if hermes_installer.get("msiSha256"):
            payload["hermesInstaller"]["msiSha256"] = hermes_installer["msiSha256"]
    return payload
