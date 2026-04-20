#!/bin/bash

# Shared LLM API caller — sourced by architect/agents/leads call.sh scripts.
#
# Usage:
#   call_llm <system> <log_name> <user_msg1> [<user_msg2> ...]
#   call_llm_with_marker <system> <log_name> <user_msg1> [<user_msg2> ...]
#
# `call_llm_with_marker` wraps `call_llm` and retries (up to MARKER_RETRIES
# times, default 3) when the response is missing the `====== MY RESPONSE ======`
# marker. Small models (Qwen 35B etc.) occasionally forget the marker; rather
# than silently salvaging garbled content, we simply ask again.
#
# Each <user_msg> becomes a separate {"role":"user","content":"..."} in the messages array.
# Pass "" as <log_name> to skip logging.
#
# Providers:
#   anthropic — Anthropic Messages API (x-api-key header)
#   openai    — OpenAI-compatible (OpenAI, Groq, Together, vLLM, LM Studio)
#   ollama    — Ollama native API (no auth, different response format)
#
# Environment (REQUIRED — resolved by detect-llm.sh in the entry scripts):
#   LLM_PROVIDER  — anthropic | openai | ollama
#   LLM_MODEL     — model id for the chosen provider
#   LLM_API_URL   — base URL (vLLM/LM Studio/Groq/Together need this)
#
# Environment (optional):
#   LLM_API_KEY       — API key (required for anthropic, optional for openai, ignored for ollama)
#   MAX_TOKENS        — max output tokens (set by calling script)
#   MARKER_RETRIES    — how many times call_llm_with_marker retries on missing
#                       marker before giving up (default 3)

MARKER="====== MY RESPONSE ======"

call_llm_with_marker() {
  local max=${MARKER_RETRIES:-3}
  local attempt=1
  local response=""
  while [ "$attempt" -le "$max" ]; do
    response=$(call_llm "$@")
    # Strip <think>...</think> reasoning blocks — thinking models often mention
    # the marker while reasoning, which is not the same as actually emitting it
    # in the response body. Fall back to the full response for non-thinking models.
    local stripped
    stripped=$(sed -n '/<\/think>/,$p' <<< "$response" | sed '1s|</think>||')
    [ -z "$stripped" ] && stripped="$response"
    # Validate that the marker is present in the think-stripped body.
    if grep -qF "$MARKER" <<< "$stripped"; then
      # Return the CLEANED body: content after the marker, marker line dropped.
      # Downstream parse.sh scripts trust this as their input — they don't need
      # to re-strip think or re-extract the marker. Full raw response (including
      # thinking) is still captured by call_llm's log file for debugging.
      sed -n "/${MARKER}/,\$ p" <<< "$stripped" | tail -n +2
      return 0
    fi
    echo "WARN  marker missing on attempt ${attempt}/${max} — retrying..." >&2
    attempt=$((attempt + 1))
  done
  echo "ERROR marker missing after ${max} attempts" >&2
  return 1
}

call_llm() {
  local system="$1" log_name="$2"
  shift 2
  local user_msgs=("$@")

  # Provider + model come from env — every entry-point script resolves them
  # via detect-llm.sh before getting here. Callers don't pass them positionally.
  local PROVIDER="${LLM_PROVIDER:?LLM_PROVIDER not set — run via one of the entry scripts in v84-docs/scripts/}"
  local MODEL="${LLM_MODEL:?LLM_MODEL not set — run via one of the entry scripts in v84-docs/scripts/}"

  # Build messages JSON array: [{"role":"user","content":"..."}, ...]
  local messages_json
  messages_json=$(printf '%s\n' "${user_msgs[@]}" | jq -Rs '
    split("\u0000") | map({role: "user", content: .})
  ' 2>/dev/null || true)

  # Simpler: build per-message JSON using jq with each arg
  messages_json="["
  local first=1 m
  for m in "${user_msgs[@]}"; do
    local esc
    esc=$(jq -Rs . <<< "$m")
    if [ "$first" = "1" ]; then
      messages_json+="{\"role\":\"user\",\"content\":${esc}}"
      first=0
    else
      messages_json+=",{\"role\":\"user\",\"content\":${esc}}"
    fi
  done
  messages_json+="]"

  local system_escaped
  system_escaped=$(jq -Rs . <<< "$system")

  local url="" body="" extract=""
  local auth_header=()

  case "$PROVIDER" in
    anthropic)
      url="https://api.anthropic.com/v1/messages"
      auth_header=(-H "x-api-key: ${LLM_API_KEY:?Set LLM_API_KEY}" -H "anthropic-version: 2023-06-01")
      body='{
        "model": "'"${MODEL}"'",
        "max_tokens": '"${MAX_TOKENS}"',
        "system": '"${system_escaped}"',
        "messages": '"${messages_json}"'
      }'
      extract='.content[0].text'
      ;;
    openai)
      url="${LLM_API_URL:-https://api.openai.com/v1}/chat/completions"
      if [ -n "${LLM_API_KEY:-}" ]; then
        auth_header=(-H "Authorization: Bearer ${LLM_API_KEY}")
      fi
      # Merge system as first message
      #{"role": "assistant", "content": "<think>"}, 
      body='{
        "model": "'"${MODEL}"'",
        "max_tokens": '"${MAX_TOKENS}"',
        "chat_template_kwargs": {
          "enable_thinking": true
        },
        "skip_special_tokens": false,
        "stream": false,
        "messages": '"$(jq -n --argjson sys "${system_escaped}" --argjson usr "${messages_json}" '
          [{role:"system", content:$sys}] + $usr
        ')"'
      }'
      extract='.choices[0].message.content'
      ;;
    ollama)
      url="${LLM_API_URL:-http://localhost:11434/api/chat}"
      body='{
        "model": "'"${MODEL}"'",
        "stream": false,
        "messages": '"$(jq -n --argjson sys "${system_escaped}" --argjson usr "${messages_json}" '
          [{role:"system", content:$sys}] + $usr
        ')"'
      }'
      extract='.message.content'
      ;;
    *)
      echo "Unknown provider: $PROVIDER (use: anthropic, openai, ollama)" >&2
      exit 1
      ;;
  esac

  # Write body to temp file to avoid "Argument list too long" for large contexts
  local tmpfile=$(mktemp)
  local rawfile=$(mktemp)
  printf '%s' "$body" > "$tmpfile"

  curl -s "$url" \
    -H "Content-Type: application/json" \
    "${auth_header[@]}" \
    -d @"$tmpfile" > "$rawfile"

  local response
  response=$(jq -r "${extract} // .error.message // .error // \"ERROR: empty response\"" < "$rawfile" \
    | awk '
      BEGIN { first=1; buf="" }
      # Strip first line if it is a fence like ``` or ```lang
      first && /^[[:space:]]*```/ { first=0; next }
      { first=0; buf = buf $0 "\n" }
      END {
        # Strip trailing fence if present
        sub(/[[:space:]]*```[[:space:]]*\n?$/, "", buf)
        printf "%s", buf
      }
    ')

  # Log the call as a single JSON document so it's easy to navigate with jq
  # (jq '.request.messages' log.json, jq '.response.choices[0].message' log.json, etc.).
  # $tmpfile is the exact request payload we POSTed (unique per call — mktemp),
  # $rawfile is the raw API response. Each is loaded as JSON if valid, otherwise
  # captured verbatim in a fallback `.raw` field so nothing is ever lost.
  if [ -n "$log_name" ]; then
    # Anchor to llm-api.sh's own path via BASH_SOURCE — $0 would resolve to the
    # caller (this file is sourced, not executed), which is why logs used to
    # scatter into whichever dir the entry script lived in.
    local log_dir="${LOG_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/yyy/logs}"
    mkdir -p "$log_dir"
    local timestamp=$(date -u +%Y%m%dT%H%M%SZ)
    local log_file="${log_dir}/${log_name}-${timestamp}.json"

    local req_json resp_json
    req_json=$(jq '.' < "$tmpfile" 2>/dev/null || jq -Rs '{raw: .}' < "$tmpfile")
    resp_json=$(jq '.' < "$rawfile" 2>/dev/null || jq -Rs '{raw: .}' < "$rawfile")

    jq -n \
      --arg url "$url" \
      --arg provider "$PROVIDER" \
      --arg model "$MODEL" \
      --arg timestamp "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --argjson request "$req_json" \
      --argjson response "$resp_json" \
      '{timestamp: $timestamp, provider: $provider, model: $model, url: $url, request: $request, response: $response}' \
      > "$log_file"
  fi

  printf '%s' "$response"

  rm -f "$tmpfile" "$rawfile"
}
