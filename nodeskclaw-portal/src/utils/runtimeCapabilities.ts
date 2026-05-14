export interface RuntimeCapabilities {
  genes: boolean
  evolutionLog: boolean
  llmConfig: boolean
  dataRoot: string
}

export interface RuntimeDefaultCapability {
  id: string
  labelKey: string
  descriptionKey: string
}

const CAPS: Record<string, RuntimeCapabilities> = {
  openclaw: { genes: true, evolutionLog: true, llmConfig: true, dataRoot: '.openclaw' },
  nanobot: { genes: false, evolutionLog: false, llmConfig: false, dataRoot: '.nanobot' },
  hermes: { genes: true, evolutionLog: false, llmConfig: true, dataRoot: '.hermes' },
}

const DEFAULT_CAPABILITIES: Record<string, RuntimeDefaultCapability[]> = {
  hermes: [
    {
      id: 'shared-files',
      labelKey: 'runtimeDefaultCapabilities.sharedFiles',
      descriptionKey: 'runtimeDefaultCapabilities.sharedFilesDesc',
    },
    {
      id: 'blackboard',
      labelKey: 'runtimeDefaultCapabilities.blackboard',
      descriptionKey: 'runtimeDefaultCapabilities.blackboardDesc',
    },
    {
      id: 'topology',
      labelKey: 'runtimeDefaultCapabilities.topology',
      descriptionKey: 'runtimeDefaultCapabilities.topologyDesc',
    },
  ],
}

export function getRuntimeCaps(runtime: string): RuntimeCapabilities {
  return CAPS[runtime] ?? CAPS.openclaw
}

export function getRuntimeDefaultCapabilities(runtime: string): RuntimeDefaultCapability[] {
  return DEFAULT_CAPABILITIES[runtime] ?? []
}
