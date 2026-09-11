#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-only
set -euo pipefail
image="$1"
evidence="$2"
mkdir -p "$evidence"
name="base-smoke-${GITHUB_RUN_ID:-local}-${GITHUB_JOB:-test}-${RANDOM}"
cleanup() {
  docker logs "$name" > "$evidence/smoke.log" 2>&1 || true
  docker rm -f "$name" >/dev/null 2>&1 || true
}
trap cleanup EXIT
docker run --rm --entrypoint /bin/sh "$image" -ec '
  test -x /init
  for tool in bash curl jq wg nft unrar; do command -v "$tool"; done
  test -f /etc/s6-overlay/s6-rc.d/init-setup/run
  test -f /etc/s6-overlay/s6-rc.d/init-wireguard/run
'
docker run --detach --name "$name" --tmpfs /config \
  -e VPN_ENABLED=false -e PRIVOXY_ENABLED=false -e UNBOUND_ENABLED=false "$image"
ready=false
for _ in {1..60}; do
  test "$(docker inspect --format '{{.State.Running}}' "$name")" = true
  if docker logs "$name" 2>&1 | grep -q 'Taking ownership of' &&
     docker exec "$name" sh -ec 'test "$(stat -c %u /config)" = 1000'; then
    ready=true
    break
  fi
  sleep 1
done
test "$ready" = true
docker exec "$name" sh -ec 'test "$(id -u hotio)" = 1000; test -d /config; test "$(stat -c %u /config)" = 1000'
docker run --rm -i --entrypoint /bin/sh "$image" -es > "$evidence/packages.txt" <<'PACKAGES'
if test -f /etc/alpine-release; then
  apk info --format json --fields name,version | jq -re '.[] | [.name, .version] | join("=")' | sort
else
  dpkg-query --showformat='${Package}=${Version}\n' --show | sort
fi
PACKAGES
test -s "$evidence/packages.txt"
printf 'Base startup, UID/config ownership and installed tools passed. VPN connectivity is not exercised.\n' > "$evidence/result.txt"
