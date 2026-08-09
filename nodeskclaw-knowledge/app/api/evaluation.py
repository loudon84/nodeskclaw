"""Evaluation API routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_db, get_member_context
from app.schemas.common import ApiResponse, PageData
from app.schemas.knowledge import (
    EvaluationCaseCreate,
    EvaluationCaseOut,
    EvaluationCaseUpdate,
    EvaluationCompareOut,
    EvaluationCompareRequest,
    EvaluationResultOut,
    EvaluationRunCreate,
    EvaluationRunOut,
    EvaluationSetCreate,
    EvaluationSetOut,
    EvaluationSetUpdate,
)
from app.schemas.principal import KnowledgePrincipal
from app.services import evaluation_service

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


@router.get("/sets", response_model=ApiResponse[PageData[EvaluationSetOut]])
async def list_sets(
    knowledge_set_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await evaluation_service.list_evaluation_sets(
        db,
        member,
        knowledge_set_id=knowledge_set_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=PageData(
            items=[EvaluationSetOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/sets", response_model=ApiResponse[EvaluationSetOut])
async def create_set(
    body: EvaluationSetCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.create_evaluation_set(
        db,
        member,
        knowledge_set_id=body.knowledge_set_id,
        name=body.name,
        description=body.description,
    )
    return ApiResponse(data=EvaluationSetOut.model_validate(row))


@router.get("/sets/{evaluation_set_id}", response_model=ApiResponse[EvaluationSetOut])
async def get_set(
    evaluation_set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.get_evaluation_set(db, member, evaluation_set_id)
    return ApiResponse(data=EvaluationSetOut.model_validate(row))


@router.patch("/sets/{evaluation_set_id}", response_model=ApiResponse[EvaluationSetOut])
async def patch_set(
    evaluation_set_id: str,
    body: EvaluationSetUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.update_evaluation_set(
        db,
        member,
        evaluation_set_id,
        name=body.name,
        description=body.description,
    )
    return ApiResponse(data=EvaluationSetOut.model_validate(row))


@router.delete("/sets/{evaluation_set_id}", response_model=ApiResponse[None])
async def delete_set(
    evaluation_set_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await evaluation_service.delete_evaluation_set(db, member, evaluation_set_id)
    return ApiResponse(data=None)


@router.get("/sets/{evaluation_set_id}/cases", response_model=ApiResponse[PageData[EvaluationCaseOut]])
async def list_cases(
    evaluation_set_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await evaluation_service.list_cases(
        db,
        member,
        evaluation_set_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=PageData(
            items=[EvaluationCaseOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.post("/sets/{evaluation_set_id}/cases", response_model=ApiResponse[EvaluationCaseOut])
async def create_case(
    evaluation_set_id: str,
    body: EvaluationCaseCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.create_case(
        db,
        member,
        evaluation_set_id,
        query=body.query,
        expected_source_file_ids=body.expected_source_file_ids,
        expected_keywords=body.expected_keywords,
        expected_answer=body.expected_answer,
    )
    return ApiResponse(data=EvaluationCaseOut.model_validate(row))


@router.get("/cases/{case_id}", response_model=ApiResponse[EvaluationCaseOut])
async def get_case(
    case_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.get_case(db, member, case_id)
    return ApiResponse(data=EvaluationCaseOut.model_validate(row))


@router.patch("/cases/{case_id}", response_model=ApiResponse[EvaluationCaseOut])
async def patch_case(
    case_id: str,
    body: EvaluationCaseUpdate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.update_case(
        db,
        member,
        case_id,
        query=body.query,
        expected_source_file_ids=body.expected_source_file_ids,
        expected_keywords=body.expected_keywords,
        expected_answer=body.expected_answer,
    )
    return ApiResponse(data=EvaluationCaseOut.model_validate(row))


@router.delete("/cases/{case_id}", response_model=ApiResponse[None])
async def delete_case(
    case_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    await evaluation_service.delete_case(db, member, case_id)
    return ApiResponse(data=None)


@router.post("/runs", response_model=ApiResponse[EvaluationRunOut])
async def create_run(
    body: EvaluationRunCreate,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.create_run(
        db,
        member,
        evaluation_set_id=body.evaluation_set_id,
        retrieval_profile_id=body.retrieval_profile_id,
    )
    return ApiResponse(data=EvaluationRunOut.model_validate(row))


@router.get("/runs", response_model=ApiResponse[PageData[EvaluationRunOut]])
async def list_runs(
    evaluation_set_id: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    items, total = await evaluation_service.list_runs(
        db,
        member,
        evaluation_set_id=evaluation_set_id,
        page=page,
        page_size=page_size,
    )
    return ApiResponse(
        data=PageData(
            items=[EvaluationRunOut.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )
    )


@router.get("/runs/{run_id}", response_model=ApiResponse[EvaluationRunOut])
async def get_run(
    run_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    row = await evaluation_service.get_run(db, member, run_id)
    return ApiResponse(data=EvaluationRunOut.model_validate(row))


@router.get("/runs/{run_id}/results", response_model=ApiResponse[list[EvaluationResultOut]])
async def get_results(
    run_id: str,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    rows = await evaluation_service.list_results(db, member, run_id)
    return ApiResponse(data=[EvaluationResultOut.model_validate(r) for r in rows])


@router.post("/compare", response_model=ApiResponse[EvaluationCompareOut])
async def compare(
    body: EvaluationCompareRequest,
    member: KnowledgePrincipal = Depends(get_member_context),
    db: AsyncSession = Depends(get_db),
):
    data = await evaluation_service.compare_profiles(
        db,
        member,
        evaluation_set_id=body.evaluation_set_id,
        profile_a_id=body.profile_a_id,
        profile_b_id=body.profile_b_id,
        run_a_id=body.run_a_id,
        run_b_id=body.run_b_id,
    )
    return ApiResponse(data=EvaluationCompareOut.model_validate(data))
