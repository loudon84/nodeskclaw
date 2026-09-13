// knowledge-frontend-contract v1.0.0
// Generated from scripts/frontend_contract_spec.py. Do not edit by hand.

export type ApiResponse<T> = {
  code: number;
  error_code?: number | null;
  message_key?: string | null;
  message: string;
  data: T | null;
  details?: Record<string, unknown>;
  message_params?: Record<string, string>;
};

export type PageData<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

export interface ErrorResponse {
  code: number;
  error_code: number;
  message_key: string;
  message: string;
  data: null;
  details?: Record<string, unknown>;
  message_params?: Record<string, string>;
}

export interface HealthReady {
  status: "ok" | "not_ready";
  checks: { database: boolean; ragflow: boolean; backend: boolean };
}

export interface KnowledgeBase {
  id: string;
  org_id: string;
  name: string;
  description?: string | null;
  embedding_model: string;
  chunk_method: string;
  status: "provisioning" | "active" | "updating" | "degraded" | "error" | "deleting";
  owner_member_id: string;
  acl_version: number;
  visibility: "private" | "department" | "organization";
  tags?: string[] | null;
  active_build_profile_id?: string | null;
  knowledge_model_id?: string | null;
  build_version: number;
}

export interface KnowledgeBaseCreate {
  name: string;
  description?: string | null;
  embedding_model?: string;
  chunk_method?: string;
  parser_config?: Record<string, unknown> | null;
  visibility?: "private" | "department" | "organization";
  tags?: string[] | null;
}

export interface KnowledgeBaseUpdate {
  name?: string;
  description?: string | null;
  tags?: string[] | null;
  visibility?: "private" | "department" | "organization";
}

export interface KnowledgeSet {
  id: string;
  org_id: string;
  name: string;
  description?: string | null;
  owner_member_id: string;
  status: "active" | "disabled";
  acl_version: number;
  visibility: "private" | "department" | "organization";
  retrieval_config?: Record<string, unknown> | null;
  usage_count: number;
  last_used_at?: unknown;
  knowledge_bases?: { knowledge_base_id: string; name?: string; weight?: number }[] | null;
}

export interface KnowledgeSetCreate {
  name: string;
  description?: string | null;
  visibility?: "private" | "department" | "organization";
  retrieval_config?: Record<string, unknown> | null;
}

export interface KnowledgeSetUpdate {
  name?: string;
  description?: string | null;
  status?: "active" | "disabled";
  visibility?: "private" | "department" | "organization";
  retrieval_config?: Record<string, unknown> | null;
}

export interface KnowledgeSetBind {
  knowledge_base_id: string;
  weight?: number;
  sort_order?: number;
}

export interface SourceFile {
  id: string;
  org_id: string;
  knowledge_base_id: string;
  file_name: string;
  mime_type?: string | null;
  owner_member_id: string;
  active_version_id?: string | null;
  status: "pending" | "active" | "updating" | "error" | "deleting";
  acl_version: number;
  last_error?: string | null;
  metadata?: Record<string, unknown>;
  metadata_revision?: number;
  archived_at?: unknown;
  parse_status?: string | null;
  chunk_count?: number | null;
  version_no?: number | null;
  source_kind?: "manual" | "connector";
  connector_id?: string | null;
  external_object_id?: string | null;
  source_uri?: string | null;
  source_path?: string | null;
  source_revision?: string | null;
  source_etag?: string | null;
  source_modified_at?: unknown;
  source_metadata?: Record<string, unknown>;
  last_synced_at?: unknown;
  sync_state?: string | null;
  archive_reason?: string | null;
}

export interface SourceFileVersion {
  id: string;
  source_file_id: string;
  version_no: number;
  file_size?: number | null;
  sha256?: string | null;
  parse_status: "pending" | "parsing" | "active" | "failed" | "superseded";
  chunk_count?: number | null;
  token_count?: number | null;
  uploaded_by_member_id?: string | null;
  activated_at?: unknown;
  superseded_at?: unknown;
  created_at?: unknown;
}

export interface IngestionJob {
  id: string;
  source_file_id: string;
  file_version_id: string;
  status: "pending" | "uploading" | "upload_unknown" | "ragflow_uploaded" | "metadata_synced" | "parse_dispatched" | "parsing" | "validating" | "active" | "failed" | "cancelled";
  progress: number;
  error_code?: string | null;
  error_message?: string | null;
  attempt_count: number;
  max_attempts: number;
  next_run_at?: unknown;
  finished_at?: unknown;
  created_by_member_id?: string | null;
}

export interface UploadAccepted {
  source_file: SourceFile;
  file_version_id: string;
  job: IngestionJob;
}

export interface IndexStateMap {
  [key: string]: { build_status: "not_built" | "building" | "ready" | "stale" | "failed" | "unsupported"; retrieval_status: "unavailable" | "ready" | "degraded" | "unsupported"; last_error?: string; validation?: Record<string, unknown>; coverage?: Record<string, unknown>; last_validated_at?: string; runtime_feature?: unknown };
}

export interface BuildJob {
  id: string;
  org_id: string;
  knowledge_base_id?: string | null;
  build_profile_id?: string | null;
  index_type?: string | null;
  trigger_reason?: string | null;
  status: "queued" | "running" | "completed" | "partial" | "failed" | "cancelled";
  progress: number;
  error_code?: string | null;
  error_message?: string | null;
  attempt_count: number;
  finished_at?: unknown;
  created_at?: unknown;
}

export interface BuildJobList {
  jobs: BuildJob[];
}

export interface BuildProfile {
  id: string;
  name: string;
  description?: string | null;
  system_key?: string | null;
  is_system?: boolean;
  index_types?: string[];
  artifact_types?: string[];
  trigger_policy?: Record<string, unknown>;
  artifact_trigger_policy?: Record<string, unknown>;
  version?: number;
}

export interface BuildProfileView {
  active_build_profile_id?: string | null;
  resolved_profile: BuildProfile;
}

export interface BuildProfileUpdate {
  build_profile_id: string;
}

export interface TriggerBuildsRequest {
  index_types: string[];
  force?: boolean;
}

export interface Acl {
  id: string;
  subject_type: "member" | "role" | "department" | "organization";
  subject_id: string;
  permission: string;
  effect: "allow" | "deny";
  created_by_member_id: string;
}

export interface AclCreate {
  subject_type: "member" | "role" | "department" | "organization";
  subject_id: string;
  permission?: string;
  effect?: "allow" | "deny";
  role?: string;
}

export interface MetadataSchema {
  fields: Record<string, unknown>[];
}

export interface RetrievalProfile {
  id: string;
  knowledge_set_id: string;
  version: number;
  config: Record<string, unknown>;
  status: "draft" | "active" | "archived";
  created_by_member_id: string;
  activated_at?: unknown;
  created_at?: unknown;
  updated_at?: unknown;
}

export interface RetrievalProfileCreate {
  config?: Record<string, unknown> | null;
}

export interface RetrievalProfileUpdate {
  config: Record<string, unknown>;
}

export interface RetrievalProfileRollback {
  publish?: boolean;
}

export interface KnowledgeApplication {
  id: string;
  org_id: string;
  name: string;
  description?: string | null;
  owner_member_id: string;
  status: "draft" | "active" | "disabled";
  answer_model?: string | null;
  active_profile_id?: string | null;
  acl_version: number;
  visibility: string;
  knowledge_set_ids: string[];
  validation_job_id?: string | null;
}

export interface KnowledgeApplicationCreate {
  name: string;
  description?: string | null;
  answer_model?: string | null;
  knowledge_set_ids?: string[];
}

export interface KnowledgeApplicationUpdate {
  name?: string;
  description?: string | null;
  answer_model?: string | null;
}

export interface KnowledgeApplicationBindSet {
  knowledge_set_id: string;
  sort_order?: number;
}

export interface KnowledgeApplicationPublish {
  promote_on_validated?: boolean;
}

export interface ApplicationReadiness {
  ready?: boolean;
  blocking?: unknown[];
  warnings?: unknown[];
  [key: string]: unknown;
}

export interface KnowledgeRelease {
  id: string;
  application_id: string;
  version: number;
  status: "draft" | "validating" | "validated" | "promoted" | "superseded" | "retired" | "failed";
  release_manifest: Record<string, unknown>;
  manifest_hash?: string | null;
  quality_snapshot_id?: string | null;
  validation_job_id?: string | null;
  created_by_member_id: string;
  promoted_at?: unknown;
  retired_at?: unknown;
  validation_error?: string | null;
  created_at?: unknown;
}

export interface KnowledgeReleaseCreate {
  retrieval_policy_revision_id?: string | null;
}

export interface ReleaseChannelState {
  id: string;
  application_id: string;
  channel: "preview" | "stable";
  active_release_id?: string | null;
  traffic_policy?: Record<string, unknown> | null;
  updated_by_member_id?: string | null;
  updated_at?: unknown;
}

export interface ReleasePromote {
  release_id: string;
}

export interface RetrievalPolicyRevision {
  id: string;
  application_id: string;
  revision_number: number;
  status: "draft" | "active" | "archived";
  query_intelligence_policy?: Record<string, unknown> | null;
  provider_policy?: Record<string, unknown> | null;
  provider_weights?: Record<string, unknown> | null;
  candidate_budget?: Record<string, unknown> | null;
  fanout_budget?: Record<string, unknown> | null;
  latency_budget?: Record<string, unknown> | null;
  fallback_policy?: Record<string, unknown> | null;
  artifact_policy?: Record<string, unknown> | null;
  fusion_policy?: Record<string, unknown> | null;
  created_by_member_id: string;
  published_at?: unknown;
  notes?: string | null;
  created_at?: unknown;
}

export interface RetrievalPolicyRevisionCreate {
  query_intelligence_policy?: Record<string, unknown> | null;
  provider_policy?: Record<string, unknown> | null;
  provider_weights?: Record<string, unknown> | null;
  candidate_budget?: Record<string, unknown> | null;
  fanout_budget?: Record<string, unknown> | null;
  latency_budget?: Record<string, unknown> | null;
  fallback_policy?: Record<string, unknown> | null;
  artifact_policy?: Record<string, unknown> | null;
  fusion_policy?: Record<string, unknown> | null;
  notes?: string | null;
}

export interface PublicEvidenceItem {
  evidence_id: string;
  knowledge_base_id?: string | null;
  source_file_id?: string | null;
  file_version_id?: string | null;
  file_name?: string | null;
  content?: string;
  score?: number | null;
  similarity?: number | null;
  weighted_score?: number | null;
  page?: number | null;
  highlight?: string | null;
  source_freshness?: string | null;
  last_synced_at?: unknown;
}

export interface ApplicationRetrievalData {
  application_id: string;
  release_id: string;
  channel: "preview" | "stable";
  manifest_hash: string;
  status?: "success" | "empty" | "degraded";
  answer_model?: string | null;
  knowledge_set_ids?: string[];
  chunks?: PublicEvidenceItem[];
}

export interface ApplicationRetrievalRequest {
  query: string;
  top_k?: number | null;
  similarity_threshold?: number | null;
  filters?: Record<string, unknown> | null;
  profile_id?: string | null;
}

export interface PlaygroundRequest {
  query: string;
  application_id?: string | null;
  knowledge_set_id?: string | null;
  profile_id?: string | null;
  filters?: Record<string, unknown> | null;
  include_trace?: boolean;
}

export interface PlaygroundResponse {
  chunks?: PublicEvidenceItem[];
  [key: string]: unknown;
}

export interface EvidenceResolve {
  evidence_id: string;
  citation_id?: string;
  message_id?: string | null;
  org_id?: string;
  issued_member_id?: string;
  evidence_type?: string;
  content?: string | null;
  source_refs?: unknown[] | null;
  origin?: string;
  knowledge_base_id: string;
  source_file_id: string;
  file_version_id: string;
  page?: number | null;
  positions?: unknown[] | null;
  score?: number | null;
  quote?: string | null;
  accessible: boolean;
  reason: string;
  source_kind?: string | null;
  connector_type?: string | null;
  connector_name?: string | null;
  source_path?: string | null;
  source_revision?: string | null;
  source_modified_at?: string | null;
  last_synced_at?: string | null;
  sync_state?: string | null;
  source_freshness?: string | null;
}

export interface QualitySnapshot {
  score_status: string;
  subscores?: Record<string, unknown>;
  data_coverage?: Record<string, unknown>;
  issues?: string[];
  calculated_at?: string;
  application_id?: string;
  [key: string]: unknown;
}

export interface QualityHistory {
  history: QualitySnapshot[];
}

export interface KnowledgeArtifact {
  id: string;
  knowledge_base_id: string;
  artifact_type: string;
  provider?: string;
  scope?: string;
  source_file_id?: string | null;
  file_version_id?: string | null;
  status: string;
  version?: number;
  active_revision_id?: string | null;
  input_manifest_hash?: string | null;
  last_built_at?: string | null;
  last_validated_at?: string | null;
  last_error?: string | null;
}

export interface ArtifactBuildRequest {
  artifact_type: string;
  source_file_id?: string | null;
  file_version_id?: string | null;
}

export interface ArtifactBuildAccepted {
  artifact_id: string;
  artifact_type: string;
  status: string;
  build_job_id?: string | null;
  input_manifest_hash?: string | null;
}

export interface ArtifactContent {
  artifact_type: string;
  content: unknown;
  [key: string]: unknown;
}
