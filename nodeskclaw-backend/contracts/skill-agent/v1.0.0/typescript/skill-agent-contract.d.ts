export type DelegationTopology = "single_agent" | "runtime_delegated";

export type PlacementRole = "central" | "edge" | "hybrid";

export type PlacementEngine = "hermes" | "connector";

export interface Placement {
  role?: PlacementRole;
  engine?: PlacementEngine;
  edge_node_id?: string | null;
}

export interface RuntimeCapabilityRef {
  name: string;
  version: string;
}

export interface InternalExecutionSnapshot {
  placement: Placement;
  delegation_topology: DelegationTopology;
  runtime_capability_ref?: RuntimeCapabilityRef;
  org_id?: string;
  user_id?: string;
  execution_context?: Record<string, unknown>;
  skill_id?: string;
  skill_release_id?: string | null;
  snapshot_hash?: string;
  [key: string]: unknown;
}
