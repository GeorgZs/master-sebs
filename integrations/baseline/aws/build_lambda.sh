#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="${DIR}/lambda_package"

rm -rf "${PKG}"
mkdir -p "${PKG}"

python3 -m pip install -r "${DIR}/lambda/requirements.txt" -t "${PKG}" --only-binary=:all: 2>/dev/null \
  || python3 -m pip install -r "${DIR}/lambda/requirements.txt" -t "${PKG}"

cp "${DIR}/lambda/handler.py" "${PKG}/"

echo "Built ${PKG} (ready for terraform archive_file)."
