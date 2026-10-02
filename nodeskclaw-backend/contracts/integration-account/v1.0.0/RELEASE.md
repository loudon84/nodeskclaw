# INTEGRATION-ACCOUNT-CONTRACT v1.0.0

This bundle freezes the public Integration Account API used by smc-copilot/apps/work.

Successful responses use the ApiResponse envelope and HTTP 200. Remote Agent success bodies stay bare JSON.

List and get do not call the provider. Disconnect attempts a provider revoke and still stores DISCONNECTED when that revoke fails. Delete does not call the provider.

Only ACTIVE accounts may be submitted as integration_account_refs. Expert external action policy is not part of this bundle.

The closed bundle digest in SHA256SUMS is the consumer pin. releaseCommitSha is the parent commit present when this bundle was sealed. implementationHeadSha is the behavior baseline and is not the same commit.
