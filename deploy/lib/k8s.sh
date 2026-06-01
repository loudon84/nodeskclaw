#!/usr/bin/env bash

diff_secret() {
  local secret_name="$1" clean_env="$2"
  if ! $KUBECTL -n "$NAMESPACE" get secret "$secret_name" &>/dev/null; then
    return 1
  fi
  local current_json
  current_json=$($KUBECTL -n "$NAMESPACE" get secret "$secret_name" -o jsonpath='{.data}')
  python3 -c "
import sys, json, base64
cur_b64 = json.loads(sys.argv[1]) if sys.argv[1] else {}
cur = {k: base64.b64decode(v).decode() for k, v in cur_b64.items()}
new = {}
with open(sys.argv[2]) as f:
    for line in f:
        line = line.strip()
        if not line or '=' not in line:
            continue
        k, v = line.split('=', 1)
        new[k] = v
added = sorted(set(new) - set(cur))
removed = sorted(set(cur) - set(new))
changed = sorted(k for k in set(new) & set(cur) if new[k] != cur[k])
if not added and not removed and not changed:
    sys.exit(10)
for k in changed:  print(f'  [变更] {k}')
for k in added:    print(f'  [新增] {k}')
for k in removed:  print(f'  [移除] {k} (将从 Secret 中删除)')
sys.exit(0)
" "$current_json" "$clean_env"
}

deploy_to_k8s() {
  local component="$1"
  local image_name; image_name="$(get_image_name "$component")"
  local comp_registry; comp_registry="$(get_component_registry "$component")"
  local image="${comp_registry}/${image_name}:${TAG}"
  local deployment; deployment="$(get_k8s_deployment "$component")"
  local container; container="$(get_k8s_container "$component")"

  log "[$(ctag "$component")] 更新 Deployment: $deployment -> $image (context: $KUBE_CONTEXT)"

  if ! $KUBECTL -n "$NAMESPACE" get deployment "$deployment" &>/dev/null; then
    warn "[$(ctag "$component")] Deployment 不存在，执行首次部署..."
    if [[ "$component" == "proxy" ]]; then
      local proxy_dir="$PROJECT_ROOT/nodeskclaw-llm-proxy/deploy"
      [[ -f "$proxy_dir/deployment.yaml" ]] && \
        sed "s|<YOUR_REGISTRY>/<YOUR_NAMESPACE>|${comp_registry}|g" "$proxy_dir/deployment.yaml" \
          | $KUBECTL -n "$NAMESPACE" apply -f -
      [[ -f "$proxy_dir/service.yaml" ]] && \
        $KUBECTL -n "$NAMESPACE" apply -f "$proxy_dir/service.yaml"
    else
      local manifest="$DEPLOY_DIR/k8s/${component}.yaml"
      [[ -f "$manifest" ]] && \
        sed "s|<YOUR_REGISTRY>/<YOUR_NAMESPACE>|${comp_registry}|g" "$manifest" \
          | $KUBECTL -n "$NAMESPACE" apply -f -
    fi
  fi

  $KUBECTL -n "$NAMESPACE" set image "deployment/$deployment" "$container=$image"

  log "[$(ctag "$component")] 等待滚动更新完成..."
  local timeout=180
  [[ "$component" == "proxy" ]] && timeout=120
  if $KUBECTL -n "$NAMESPACE" rollout status "deployment/$deployment" --timeout="${timeout}s"; then
    ok "[$(ctag "$component")] 部署完成"
  else
    err "[$(ctag "$component")] 部署超时，请检查 Pod 状态"
    $KUBECTL -n "$NAMESPACE" get pods -l "app=$deployment"
    return 1
  fi
}
