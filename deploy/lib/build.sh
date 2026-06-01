#!/usr/bin/env bash

build_and_push() {
  local component="$1"
  local image_name; image_name="$(get_image_name "$component")"
  local comp_registry; comp_registry="$(get_component_registry "$component")"
  local image="${comp_registry}/${image_name}:${TAG}"
  local context; context="$(get_build_context "$component")"
  local dockerfile; dockerfile="$(get_dockerfile "$component")"
  local extra_args=""

  if [[ "${CE_ONLY:-true}" != true && "$component" != "proxy" && -d "$PROJECT_ROOT/ee" ]]; then
    local ee_df
    ee_df="$(mktemp)"
    case "$component" in
      backend)
        cat "$dockerfile" > "$ee_df"
        echo 'COPY ee/ ./ee/' >> "$ee_df"
        dockerfile="$ee_df"
        ;;
      admin)
        if [[ ! -d "$PROJECT_ROOT/ee/nodeskclaw-frontend" ]]; then
          warn "[$(ctag "$component")] ee/nodeskclaw-frontend 不存在，跳过 admin 构建"
          return 0
        fi
        ;;
      portal)
        cat > "$ee_df" <<EODF
ARG NPM_REGISTRY=""
ARG ALPINE_MIRROR=""

FROM node:22-alpine AS builder
ARG NPM_REGISTRY
ARG ALPINE_MIRROR
RUN if [ -n "\$ALPINE_MIRROR" ]; then \
      sed -i "s|dl-cdn.alpinelinux.org|\${ALPINE_MIRROR}|g" /etc/apk/repositories; \
    fi && \
    if [ -n "\$NPM_REGISTRY" ]; then npm config set registry "\$NPM_REGISTRY"; fi
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
COPY --from=ee frontend/portal/ /ee/frontend/portal/
ARG VITE_APP_VERSION=dev
ENV VITE_APP_VERSION=\$VITE_APP_VERSION
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
EODF
        dockerfile="$ee_df"
        extra_args="--build-context ee=$PROJECT_ROOT/ee"
        ;;
    esac
    log "[$(ctag "$component")] 检测到 ee/ 目录，构建 EE 版镜像"
  elif [[ "$component" == "admin" && ! -d "$PROJECT_ROOT/ee" ]]; then
    warn "[$(ctag "$component")] ee/ 目录不存在（CE 版本），跳过 admin 构建"
    return 0
  fi

  case "$component" in
    backend)
      extra_args="$extra_args --build-arg APP_VERSION=${TAG}"
      ;;
    portal|admin)
      extra_args="$extra_args --build-arg VITE_APP_VERSION=${TAG}"
      ;;
  esac

  log "[$(ctag "$component")] 构建镜像: $image"
  if ! docker build --platform linux/amd64 \
    ${NO_CACHE:-} \
    $extra_args \
    -f "$dockerfile" \
    --build-arg http_proxy= \
    --build-arg https_proxy= \
    --build-arg HTTP_PROXY= \
    --build-arg HTTPS_PROXY= \
    --build-arg PIP_INDEX_URL="${PIP_INDEX_URL:-}" \
    --build-arg PIP_TRUSTED_HOST="${PIP_TRUSTED_HOST:-}" \
    --build-arg NPM_REGISTRY="${NPM_REGISTRY:-}" \
    --build-arg APT_MIRROR="${APT_MIRROR:-}" \
    --build-arg ALPINE_MIRROR="${ALPINE_MIRROR:-}" \
    -t "$image" \
    "$context"; then
    err "[$(ctag "$component")] 镜像构建失败"
    return 1
  fi

  log "[$(ctag "$component")] 推送镜像..."
  if ! docker push "$image"; then
    err "[$(ctag "$component")] 镜像推送失败"
    return 1
  fi

  ok "[$(ctag "$component")] $image"
}
