from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api import genes
from app.core.security import AuthActor, _auth_actor
from app.schemas.gene import ApplyGenomeRequest, InstallGeneRequest, UninstallGeneRequest


@pytest.fixture
def agent_actor():
    token = _auth_actor.set(AuthActor("agent", "inst-1", "Hermes"))
    try:
        yield
    finally:
        _auth_actor.reset(token)


def _org_ctx(org_id: str | None = "org-instance"):
    return SimpleNamespace(id="user-1"), SimpleNamespace(id=org_id)


async def test_agent_instance_genes_uses_effective_instance_org(monkeypatch, agent_actor):
    db = object()
    get_instance_genes = AsyncMock(return_value=[])
    monkeypatch.setattr(genes.gene_service, "get_instance_genes", get_instance_genes)

    response = await genes.instance_genes("inst-1", db=db, org_ctx=_org_ctx())

    assert response.data == []
    get_instance_genes.assert_awaited_once_with(db, "inst-1", "org-instance")


async def test_agent_instance_skills_uses_effective_instance_org(monkeypatch, agent_actor):
    db = object()
    get_instance_skills = AsyncMock(return_value=[])
    monkeypatch.setattr(genes.gene_service, "get_instance_skills", get_instance_skills)

    response = await genes.instance_skills("inst-1", db=db, org_ctx=_org_ctx())

    assert response.data == []
    get_instance_skills.assert_awaited_once_with(db, "inst-1", "org-instance")


async def test_agent_install_gene_uses_effective_instance_org(monkeypatch, agent_actor):
    db = object()
    install_gene = AsyncMock(return_value={"status": "installed"})
    monkeypatch.setattr(genes.gene_service, "install_gene", install_gene)

    response = await genes.install_gene(
        "inst-1",
        InstallGeneRequest(gene_slug="deskclaw-gene-discovery"),
        db=db,
        org_ctx=_org_ctx(),
    )

    assert response.data == {"status": "installed"}
    install_gene.assert_awaited_once_with(
        db,
        "inst-1",
        "deskclaw-gene-discovery",
        org_id="org-instance",
    )


async def test_agent_uninstall_gene_uses_effective_instance_org(monkeypatch, agent_actor):
    db = object()
    uninstall_gene = AsyncMock(return_value={"status": "uninstalled"})
    monkeypatch.setattr(genes.gene_service, "uninstall_gene", uninstall_gene)

    response = await genes.uninstall_gene(
        "inst-1",
        UninstallGeneRequest(gene_id="gene-1"),
        db=db,
        org_ctx=_org_ctx(),
    )

    assert response.data == {"status": "uninstalled"}
    uninstall_gene.assert_awaited_once_with(db, "inst-1", "gene-1", org_id="org-instance")


async def test_agent_apply_genome_uses_effective_instance_org(monkeypatch, agent_actor):
    db = object()
    apply_genome = AsyncMock(return_value={"status": "applied"})
    monkeypatch.setattr(genes.gene_service, "apply_genome", apply_genome)

    response = await genes.apply_genome(
        "inst-1",
        ApplyGenomeRequest(genome_id="genome-1"),
        db=db,
        org_ctx=_org_ctx(),
    )

    assert response.data == {"status": "applied"}
    apply_genome.assert_awaited_once_with(db, "inst-1", "genome-1", "org-instance")


async def test_agent_gene_route_rejects_other_instance(monkeypatch, agent_actor):
    db = object()
    install_gene = AsyncMock()
    monkeypatch.setattr(genes.gene_service, "install_gene", install_gene)

    with pytest.raises(HTTPException) as exc:
        await genes.install_gene(
            "inst-2",
            InstallGeneRequest(gene_slug="deskclaw-gene-discovery"),
            db=db,
            org_ctx=_org_ctx(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["message_key"] == "errors.instance.agent_access_forbidden"
    install_gene.assert_not_awaited()
