# Soft Delete

所有业务删除必须是逻辑删除（`deleted_at`），禁止 `db.delete()` 与裸 `DELETE FROM`；唯一约束只用 Partial Unique Index。

该决策保证「删除后再创建同键」不撞全表 UniqueConstraint，并让审计与恢复仍可见历史行。

## Rules

查询默认过滤 `deleted_at IS NULL`（或 `not_deleted(Model)`）；级联删除须手动软删子记录。

唯一索引形态：`Index(..., unique=True, postgresql_where=text("deleted_at IS NULL"))`。ORM 基类：[[nodeskclaw-backend/app/models/base.py#BaseModel]]；软删方法：[[nodeskclaw-backend/app/models/base.py#BaseModel#soft_delete]]。

## Why Not Hard Delete

物理删除会破坏审计、用量追溯与「删后重建」产品路径，并与多 Agent 并发改库的协作方式冲突。

例外不存在于常规业务 API；运维级物理清理若出现，必须单独设计且超出默认代码路径。
