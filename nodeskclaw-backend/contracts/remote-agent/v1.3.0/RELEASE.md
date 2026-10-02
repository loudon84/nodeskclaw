# REMOTE-AGENT-PROVIDER-CONTRACT v1.3.0

This bundle adds optional attachment_refs on direct expert runs.

A consumer uploads a file with POST /api/v1/attachments, then submits the returned att_ reference on POST /api/v1/remote-agent/runs. The Work interface is a later consumer and is not implemented by this bundle.

attachment_refs is optional. Duplicate references are allowed by the schema and are deduplicated before proof. The success response does not echo attachment metadata.

ACP (Agent Client Protocol) is unsupported in this release. This bundle does not define an ACP transport, stdio bridge, or partial ACP event mapping.

The v1.0.0, v1.1.0, and v1.2.0 bundles in the sibling directories stay immutable. Skill runs remain on the frozen SKILL-RUN-CONTRACT v1.6.0 bundle.

The consumer pin for smc-copilot/apps/work is the SHA256SUMS file in this directory. Live attachment execution without a per-run Hermes workspace remains a production gate and is not marked passed by this bundle.

releaseCommitSha and implementationHeadSha record the parent commit present when this bundle was sealed. They are not the consumer pin.
