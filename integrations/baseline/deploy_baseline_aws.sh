#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TF_DIR="${TF_DIR:-${SCRIPT_DIR}/aws}"

usage() {
  cat <<USAGE
Usage: $(basename "$0") <init|plan|apply|destroy|output|fmt|validate>

Env:
  TF_DIR=<path>        Override terraform directory (default: integrations/baseline/aws)
  TF_VARS_FILE=<file>  Optional tfvars file path
USAGE
}

if [[ ! -d "${TF_DIR}" ]]; then
  echo "Terraform dir not found: ${TF_DIR}" >&2
  exit 1
fi

CMD="${1:-}"
if [[ -z "${CMD}" ]]; then
  usage
  exit 1
fi

TF_ARGS=()
if [[ -n "${TF_VARS_FILE:-}" ]]; then
  TF_ARGS+=("-var-file=${TF_VARS_FILE}")
fi

case "${CMD}" in
  init)
    terraform -chdir="${TF_DIR}" init
    ;;
  plan)
    terraform -chdir="${TF_DIR}" plan "${TF_ARGS[@]}"
    ;;
  apply)
    terraform -chdir="${TF_DIR}" apply "${TF_ARGS[@]}"
    ;;
  destroy)
    terraform -chdir="${TF_DIR}" destroy "${TF_ARGS[@]}"
    ;;
  output)
    terraform -chdir="${TF_DIR}" output
    ;;
  fmt)
    terraform -chdir="${TF_DIR}" fmt -recursive
    ;;
  validate)
    terraform -chdir="${TF_DIR}" validate
    ;;
  *)
    usage
    exit 1
    ;;
esac
