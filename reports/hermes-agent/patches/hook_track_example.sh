#!/usr/bin/env bash
# 可选：在实例侧包装「写文件」工具后，显式登记产物路径。
# 用法：
#   export HERMES_RUN_ID=<run_id>
#   ./hook_track_example.sh /workspace/out/report.md
#
# 需要容器内已安装 hermes-output-artifacts，且 Python 能 import。

set -euo pipefail
PATH_TO_TRACK="${1:?path required}"
RUN_ID="${HERMES_RUN_ID:?HERMES_RUN_ID required}"

python - <<PY
from hermes_output_artifacts.plugin import track_workspace_file
track_workspace_file("${RUN_ID}", r"""${PATH_TO_TRACK}""")
print("[output-artifacts] tracked", r"""${PATH_TO_TRACK}""")
PY
