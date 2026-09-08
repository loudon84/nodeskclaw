# SKILL-RUN-CONTRACT v1.4.0

Cumulative Public Skill Run contract. Adds Public Attachment upload and opaque org/user refs on frozen v1.3.0.
approvalDecision=supported; approval=supported; attachments=supported; approvalExpiry=unsupported.
Public upload is POST /api/v1/attachments. Binding is params.client_context.attachment_refs only.
Accepted structuredContent includes opaque attachment_refs. wireBreaking=false.
Do not rewrite frozen v1.2.1 or v1.3.0. Tag name is skill-run-contract-v1.4.0.
