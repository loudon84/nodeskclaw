# Managed Credential Mode

NODESKCLAW_CREDENTIAL_MODE=managed

Main injects NODESKCLAW_ACCESS_TOKEN and NODESKCLAW_REFRESH_TOKEN.
Adapter must not read or write OS keyring.
Adapter must not prompt nodeskclaw-acp login.
401 refreshes once in memory and retries the logical request once.
Tokens must not travel on ACP JSON-RPC.
