#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="${DIR}/lambda_package"

rm -rf "${PKG}"
mkdir -p "${PKG}"

python3 -m pip install -r "${DIR}/lambda/requirements.txt" -t "${PKG}" --only-binary=:all: 2>/dev/null \
  || python3 -m pip install -r "${DIR}/lambda/requirements.txt" -t "${PKG}"

cp "${DIR}/lambda/handler.py" "${PKG}/"

# Copy the SeBS benchmark function so handler.py can import it.
BENCH_FN="${DIR}/../../../benchmarks/900.stateful/baseline-lambda-redis/python/function.py"
if [[ -f "${BENCH_FN}" ]]; then
  cp "${BENCH_FN}" "${PKG}/function.py"
else
  echo "ERROR: benchmark function not found at ${BENCH_FN}" >&2
  exit 1
fi

echo "Built ${PKG} (ready for terraform archive_file)."
