# Autoscan container

Container packaging based on [hotio/autoscan](https://github.com/hotio/autoscan), running [Cloudbox/autoscan](https://github.com/Cloudbox/autoscan). GPL-3.0 licensing and upstream attribution are retained.

Documentation: <https://web.edb.fi/containers/autoscan/>.

Images: `ghcr.io/edbfi/autoscan:release` (`latest`) and `:nightly`.
Release preserves 1.4.0; nightly is the pinned source revision in `meta.json`, published manually after review. It does not automatically track new commits.

Mount persistent storage at `/config` for `config.yml`, `autoscan.db` and `autoscan.log`. HTTP listens on port 3030. The bundled starter configuration enables a Sonarr trigger; configure your own targets and authentication before exposing webhooks. Set both `authentication.username` and `authentication.password` in `config.yml` to enable upstream Basic Auth. The public `/health` endpoint is intentionally unauthenticated.

Both native amd64 and arm64 builds verify source checksums, Go modules, startup, HTTP/authentication, scan persistence and file ownership before publication. Source and builder pins are updated together through reviewed changes. No live media-server or VPN connectivity is implied by these isolated checks.
