#!/bin/bash

# Probe common LLM endpoints and emit `export` lines for LLM_API_URL,
# LLM_PROVIDER, and LLM_MODEL. Intended to be sourced or eval'd.
#
# Usage:
#   eval "$(scripts/detect-llm.sh)"
#   bash scripts/cycle/run.sh 3 15 "$LLM_PROVIDER" "$LLM_MODEL"
#
# Order of candidates:
#   1. LLM_API_URL (if set)  — honor whatever the user pointed at
#   2. http://localhost:11434      — Ollama native (also exposes /v1)
#   3. http://localhost:11434/v1   — same host, OpenAI-compat
#   4. http://localhost:8000/v1    — vLLM default
#   5. http://localhost:1234/v1    — LM Studio default
#
# Detection:
#   - GET {URL}/models  → OpenAI-compatible (openai provider).
#     Accepts vLLM, LM Studio, Ollama-compat, OpenAI, Groq, Together.
#   - GET {URL_ROOT}/api/tags → Ollama native (ollama provider).
#   - If both work, prefer `openai` (smaller surface, identical everywhere).
#
# Model: first `id` in /v1/models (or first `name` in /api/tags).
# Overrides: LLM_API_URL, LLM_PROVIDER, LLM_MODEL env vars short-circuit probes
# (LLM_API_URL becomes the only candidate; LLM_PROVIDER/LLM_MODEL win over
# whatever is detected).

set -eu

probe_openai() {
  # Returns 0 and echoes first model id; returns 1 on failure.
  local url="$1"
  local body
  body=$(curl -s -m 3 "${url%/}/models" 2>/dev/null) || return 1
  local id
  id=$(echo "$body" | jq -r '.data[0].id // empty' 2>/dev/null) || return 1
  [ -n "$id" ] || return 1
  echo "$id"
}

probe_ollama() {
  # Returns 0 and echoes first model name; returns 1 on failure.
  local url="$1"
  # Normalize: strip trailing /v1 so we can hit /api/tags at the root.
  local root="${url%/v1}"
  local body
  body=$(curl -s -m 3 "${root%/}/api/tags" 2>/dev/null) || return 1
  local name
  name=$(echo "$body" | jq -r '.models[0].name // empty' 2>/dev/null) || return 1
  [ -n "$name" ] || return 1
  echo "$name"
}

detect_one() {
  local url="$1"
  local model
  if model=$(probe_openai "$url"); then
    echo "openai|$url|$model"
    return 0
  fi
  if model=$(probe_ollama "$url"); then
    # Normalize URL for ollama provider — llm-api.sh uses the root, not /v1.
    local root="${url%/v1}"
    echo "ollama|$root|$model"
    return 0
  fi
  return 1
}

# Short-circuit: if all three env vars are already set, trust them and skip
# probing entirely. This is what happens inside cycle/run.sh for rounds 2+:
# the first round detects, later rounds reuse the exported values.
if [ -n "${LLM_API_URL:-}" ] && [ -n "${LLM_PROVIDER:-}" ] && [ -n "${LLM_MODEL:-}" ]; then
  echo "export LLM_API_URL='${LLM_API_URL}'"
  echo "export LLM_PROVIDER='${LLM_PROVIDER}'"
  echo "export LLM_MODEL='${LLM_MODEL}'"
  echo "# cached: ${LLM_PROVIDER} @ ${LLM_API_URL} → ${LLM_MODEL}" >&2
  exit 0
fi

candidates=()
[ "${LLM_API_URL:-}" != "" ] && candidates+=("$LLM_API_URL")
candidates+=(
  "http://localhost:11434"
  "http://localhost:11434/v1"
  "http://localhost:8000/v1"
  "http://localhost:1234/v1"
)

found=""
for url in "${candidates[@]}"; do
  if found=$(detect_one "$url" 2>/dev/null); then
    break
  fi
done

if [ -z "$found" ]; then
  echo "ERROR: no LLM endpoint reachable." >&2
  echo "       Tried: ${candidates[*]}" >&2
  echo "       Set LLM_API_URL / LLM_PROVIDER / LLM_MODEL, or run a local LLM." >&2
  exit 1
fi

provider="${found%%|*}"
rest="${found#*|}"
url="${rest%%|*}"
model="${rest#*|}"

# Let explicit env overrides win (partial override case — one var set, others not).
provider="${LLM_PROVIDER:-$provider}"
model="${LLM_MODEL:-$model}"
url="${LLM_API_URL:-$url}"

echo "export LLM_API_URL='${url}'"
echo "export LLM_PROVIDER='${provider}'"
echo "export LLM_MODEL='${model}'"
echo "# detected: ${provider} @ ${url} → ${model}" >&2
