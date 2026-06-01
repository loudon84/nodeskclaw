#!/bin/bash
# common.sh — DeskClaw Docker 镜像构建公共函数
#
# 使用方式: 在 build.sh 中 source 本文件
#   source "${SCRIPT_DIR}/common.sh"

set -e

# ── OCI 镜像仓库配置 ──────────────────────────────
REGISTRY_HOST="nodesk-center-cn-beijing.cr.volces.com"
REGISTRY_NAMESPACE="public"

registry_for() {
  local runtime="$1"
  echo "${REGISTRY_HOST}/${REGISTRY_NAMESPACE}/deskclaw-${runtime}"
}

# ── 日志 ────────────────────────────────────────
log_info()    { echo "[INFO]  $*"; }
log_error()   { echo "[ERROR] $*" >&2; }
log_success() { echo "[OK]    $*"; }

# ── Docker 检查 ─────────────────────────────────
check_docker() {
  if ! command -v docker &>/dev/null; then
    log_error "docker 未安装"
    exit 1
  fi
}

# ── 构建镜像 ─────────────────────────────────────
# docker_build <context_dir> <tag> [build_args...]
docker_build() {
  local context_dir="$1"; shift
  local tag="$1"; shift
  local build_args=("$@")

  docker build --platform linux/amd64 \
    --build-arg http_proxy= \
    --build-arg https_proxy= \
    --build-arg HTTP_PROXY= \
    --build-arg HTTPS_PROXY= \
    --build-arg PIP_INDEX_URL="${PIP_INDEX_URL:-}" \
    --build-arg PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-}" \
    --build-arg NPM_REGISTRY="${NPM_REGISTRY:-}" \
    --build-arg APT_MIRROR="${APT_MIRROR:-}" \
    --build-arg ALPINE_MIRROR="${ALPINE_MIRROR:-}" \
    "${build_args[@]}" \
    -t "${tag}" \
    "${context_dir}"
}

# ── 推送镜像 ─────────────────────────────────────
docker_push() {
  local tag="$1"
  log_info "推送镜像: ${tag}"
  docker push "${tag}"
}

# ── 构建摘要 ─────────────────────────────────────
print_build_summary() {
  local name="$1"
  local version="$2"
  local registry="$3"
  local platform="${4:-linux/amd64}"
  local mode="${5:-base}"

  echo ""
  echo "=========================================="
  echo "  ${name} 镜像构建"
  echo "=========================================="
  echo "  版本:   ${version}"
  echo "  仓库:   ${registry}"
  echo "  平台:   ${platform}"
  echo "  模式:   ${mode}"
  echo "=========================================="
  echo ""
}

# ── 完成摘要 ─────────────────────────────────────
print_done() {
  local full_tag="$1"
  echo ""
  echo "=========================================="
  echo "  完成"
  echo "=========================================="
  echo "  ${full_tag}"
  echo "=========================================="
}

# ── 解析通用参数 ─────────────────────────────────
# 调用后设置: VERSION, BUILD_ONLY, SKIP_VERIFY, WITH_SECURITY, BASE_TAG, MIRRORS
parse_common_args() {
  VERSION=""
  BUILD_ONLY=false
  SKIP_VERIFY=false
  WITH_SECURITY=false
  BASE_TAG=""
  MIRRORS=""

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --version)
        VERSION="$2"
        shift 2
        ;;
      --build-only)
        BUILD_ONLY=true
        shift
        ;;
      --skip-verify)
        SKIP_VERIFY=true
        shift
        ;;
      --with-security)
        WITH_SECURITY=true
        shift
        ;;
      --base-tag)
        BASE_TAG="$2"
        shift 2
        ;;
      --mirrors)
        MIRRORS="$2"
        shift 2
        ;;
      *)
        echo "未知参数: $1"
        echo "用法: $0 [--version <ver>] [--build-only] [--skip-verify] [--with-security] [--base-tag <tag>] [--mirrors <preset>]"
        exit 1
        ;;
    esac
  done

  if [ "${WITH_SECURITY}" = true ] && [ -z "${BASE_TAG}" ]; then
    log_error "--with-security 需要 --base-tag 指定 base 镜像 tag"
    exit 1
  fi
}

# ── 镜像源预设加载 ───────────────────────────────
load_mirrors() {
  if [ -n "${MIRRORS}" ]; then
    local project_root
    project_root="$(cd "${SCRIPT_DIR}/.." && pwd)"
    local mirrors_file="${project_root}/deploy/mirrors/${MIRRORS}.env"
    if [ ! -f "${mirrors_file}" ]; then
      log_error "镜像预设不存在: ${mirrors_file}"
      echo "可用预设:"
      for f in "${project_root}/deploy/mirrors/"*.env; do
        [ -f "$f" ] && echo "  $(basename "$f" .env)"
      done
      exit 1
    fi
    source "${mirrors_file}"
    log_info "使用镜像预设: ${MIRRORS}"
  fi
}
