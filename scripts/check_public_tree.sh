#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

if git grep -nE \
  '(BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY|Authorization:[[:space:]]|Bearer[[:space:]]+[A-Za-z0-9._-]{12,}|controlToken[=:][^[:space:]]+)' \
  -- . ':!scripts/check_public_tree.sh'; then
  printf '%s\n' "Potential credential material found in the tracked tree." >&2
  exit 1
fi

if git grep -nE \
  '(spark-af94|anteater-pumpkinseed|builderberg|100\.105\.225\.91|100\.106\.122\.35|100\.113\.242\.55|192\.168\.10\.54|/home/chrisvoncsefalvay|/home/hcltech)' \
  -- . ':!scripts/check_public_tree.sh'; then
  printf '%s\n' "Private host identity found in the tracked tree." >&2
  exit 1
fi

if git ls-files | grep -E \
  '(^|/)(outputs|evidence|certs|runtime|sdk|archives)/|\.(key|pem|p12|whl|tgz|tar\.gz|usdc)$'; then
  printf '%s\n' "A generated runtime, credential or evidence file is tracked." >&2
  exit 1
fi

printf '%s\n' "Public-tree checks passed."
