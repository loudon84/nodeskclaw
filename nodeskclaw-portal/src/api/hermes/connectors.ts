import api from '@/services/api'

function unwrapEnvelope<T>(body: unknown): T {
  if (body && typeof body === 'object' && 'data' in (body as Record<string, unknown>)) {
    return (body as { data: T }).data
  }
  return body as T
}

export type ConnectorKind = 'mcp' | 'rest' | 'db'
export type ConnectorPlacement = 'central' | 'edge'

export interface ConnectorDefinition {
  id: string
  org_id: string
  name: string
  kind: ConnectorKind | string
  title: string | null
  description: string | null
  created_by: string | null
  created_at: string | null
  updated_at: string | null
  instance_count?: number
  public_tool_count?: number
}

export interface ConnectorDefinitionCreate {
  name: string
  kind: ConnectorKind
  title?: string | null
  description?: string | null
}

export interface ConnectorDefinitionUpdate {
  title?: string | null
  description?: string | null
}

export interface ConnectorInstance {
  id: string
  org_id: string
  definition_id: string
  name: string
  placement: ConnectorPlacement | string
  edge_node_id: string | null
  secret_ref_id: string | null
  config: Record<string, unknown> | null
  is_active: boolean
  created_by: string | null
  created_at: string | null
  secret_ref_name?: string | null
}

export interface ConnectorInstanceCreate {
  name: string
  placement?: ConnectorPlacement
  edge_node_id?: string | null
  secret_ref_id?: string | null
  config?: Record<string, unknown> | null
  is_active?: boolean
}

export interface ConnectorInstanceUpdate {
  name?: string
  placement?: ConnectorPlacement
  edge_node_id?: string | null
  secret_ref_id?: string | null
  config?: Record<string, unknown> | null
  is_active?: boolean
}

export interface ConnectorTool {
  id: string
  org_id: string
  instance_id: string
  tool_name: string
  title: string | null
  description: string | null
  input_schema: Record<string, unknown> | null
  is_public: boolean
  extra_metadata: Record<string, unknown> | null
  created_at: string | null
}

export interface ConnectorToolCreate {
  tool_name: string
  title?: string | null
  description?: string | null
  input_schema?: Record<string, unknown> | null
  is_public?: boolean
  extra_metadata?: Record<string, unknown> | null
}

export interface ConnectorToolUpdate {
  title?: string | null
  description?: string | null
  input_schema?: Record<string, unknown> | null
  is_public?: boolean
  extra_metadata?: Record<string, unknown> | null
}

export interface SecretRef {
  id: string
  org_id: string
  name: string
  edge_node_id: string | null
  description: string | null
  created_by: string | null
  created_at: string | null
}

export interface SecretRefCreate {
  name: string
  edge_node_id?: string | null
  description?: string | null
}

export interface EdgeNode {
  id: string
  org_id: string
  name: string
  status: string
  last_heartbeat_at: string | null
  created_by: string | null
  created_at: string | null
}

export interface EdgeNodeCreateResult {
  node: EdgeNode
  bootstrap: string
  expires_at: string
}

export interface ListResult<T> {
  items: T[]
  total: number
}

export async function listConnectorDefinitions(): Promise<ListResult<ConnectorDefinition>> {
  const { data } = await api.get('/hermes/connectors/definitions')
  return unwrapEnvelope<ListResult<ConnectorDefinition>>(data)
}

export async function createConnectorDefinition(
  body: ConnectorDefinitionCreate,
): Promise<ConnectorDefinition> {
  const { data } = await api.post('/hermes/connectors/definitions', body)
  return unwrapEnvelope<ConnectorDefinition>(data)
}

export async function getConnectorDefinition(id: string): Promise<ConnectorDefinition> {
  const { data } = await api.get(`/hermes/connectors/definitions/${id}`)
  return unwrapEnvelope<ConnectorDefinition>(data)
}

export async function updateConnectorDefinition(
  id: string,
  body: ConnectorDefinitionUpdate,
): Promise<ConnectorDefinition> {
  const { data } = await api.patch(`/hermes/connectors/definitions/${id}`, body)
  return unwrapEnvelope<ConnectorDefinition>(data)
}

export async function deleteConnectorDefinition(id: string): Promise<void> {
  await api.delete(`/hermes/connectors/definitions/${id}`)
}

export async function listConnectorInstances(
  definitionId?: string,
): Promise<ListResult<ConnectorInstance>> {
  const { data } = await api.get('/hermes/connectors/instances', {
    params: definitionId ? { definition_id: definitionId } : undefined,
  })
  return unwrapEnvelope<ListResult<ConnectorInstance>>(data)
}

export async function createConnectorInstance(
  definitionId: string,
  body: ConnectorInstanceCreate,
): Promise<ConnectorInstance> {
  const { data } = await api.post(`/hermes/connectors/definitions/${definitionId}/instances`, body)
  return unwrapEnvelope<ConnectorInstance>(data)
}

export async function updateConnectorInstance(
  id: string,
  body: ConnectorInstanceUpdate,
): Promise<ConnectorInstance> {
  const { data } = await api.patch(`/hermes/connectors/instances/${id}`, body)
  return unwrapEnvelope<ConnectorInstance>(data)
}

export async function deleteConnectorInstance(id: string): Promise<void> {
  await api.delete(`/hermes/connectors/instances/${id}`)
}

export async function listConnectorTools(instanceId: string): Promise<ListResult<ConnectorTool>> {
  const { data } = await api.get(`/hermes/connectors/instances/${instanceId}/tools`)
  return unwrapEnvelope<ListResult<ConnectorTool>>(data)
}

export async function createConnectorTool(
  instanceId: string,
  body: ConnectorToolCreate,
): Promise<ConnectorTool> {
  const { data } = await api.post(`/hermes/connectors/instances/${instanceId}/tools`, body)
  return unwrapEnvelope<ConnectorTool>(data)
}

export async function updateConnectorTool(
  id: string,
  body: ConnectorToolUpdate,
): Promise<ConnectorTool> {
  const { data } = await api.patch(`/hermes/connectors/tools/${id}`, body)
  return unwrapEnvelope<ConnectorTool>(data)
}

export async function deleteConnectorTool(id: string): Promise<void> {
  await api.delete(`/hermes/connectors/tools/${id}`)
}

export async function listSecretRefs(): Promise<ListResult<SecretRef>> {
  const { data } = await api.get('/hermes/connectors/secret-refs')
  return unwrapEnvelope<ListResult<SecretRef>>(data)
}

export async function createSecretRef(body: SecretRefCreate): Promise<SecretRef> {
  const { data } = await api.post('/hermes/connectors/secret-refs', body)
  return unwrapEnvelope<SecretRef>(data)
}

export async function listEdgeNodes(): Promise<ListResult<EdgeNode>> {
  const { data } = await api.get('/hermes/edge-nodes')
  return unwrapEnvelope<ListResult<EdgeNode>>(data)
}

export async function createEdgeNode(body: { name: string }): Promise<EdgeNodeCreateResult> {
  const { data } = await api.post('/hermes/edge-nodes', body)
  return unwrapEnvelope<EdgeNodeCreateResult>(data)
}

export async function disableEdgeNode(nodeId: string): Promise<EdgeNode> {
  const { data } = await api.post(`/hermes/edge-nodes/${nodeId}/disable`)
  return unwrapEnvelope<EdgeNode>(data)
}

export async function enableEdgeNode(nodeId: string): Promise<EdgeNode> {
  const { data } = await api.post(`/hermes/edge-nodes/${nodeId}/enable`)
  return unwrapEnvelope<EdgeNode>(data)
}

export async function rotateEdgeNode(nodeId: string): Promise<EdgeNode> {
  const { data } = await api.post(`/hermes/edge-nodes/${nodeId}/rotate`)
  return unwrapEnvelope<EdgeNode>(data)
}

export async function revokeEdgeNode(nodeId: string): Promise<EdgeNode> {
  const { data } = await api.post(`/hermes/edge-nodes/${nodeId}/revoke`)
  return unwrapEnvelope<EdgeNode>(data)
}
