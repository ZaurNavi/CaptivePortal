#!/usr/bin/env bash
# Owner-only independent TEST-GATE-PLATFORM-01/P1-v1; native clean Git required.
# Args: PYTHON REPO HEAD TREE OUTPUT APPROVED_ENVIRONMENT_LOCK_SHA256
if [ "$#" -ne 6 ]; then exit 2; fi
runner_dir="$(cd -- "$(dirname -- "$0")" && pwd)" || exit 2
env -i HOME="$HOME" PATH="/usr/bin:/bin" LANG=C.UTF-8 \
  PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHONNOUSERSITE=1 \
  "$1" -I -B "$runner_dir/gate-preflight-v1.py" --repo "$2" --head "$3" --tree "$4" \
  --output "$5" --run-owner-gate --launcher "$runner_dir/run-linux-platform-gates-v1.sh" --lock-sha256 "$6"
status=$?
exit "$status"
