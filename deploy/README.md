# NAS operator runbook

This is an implementation artifact, not an authorization to deploy before the
Frame arrives.

1. Clone this repository on the NAS and copy `.env.example` to `.env`.
2. Set `FRAME_ART_DATA_DIR` to a directory on the primary NAS drive (for
   example, `/srv/your-primary-volume/Art/frame-art`). Keep this
   directory out of Git; it contains the Samsung pairing token and SQLite data.
3. Reserve a stable LAN IP for the TV, then set `FRAME_ART_TV_HOST` after the
   first on-NAS pairing test.
4. Start with `docker compose up -d --build`. Confirm only
   `127.0.0.1:8033` listens on the NAS.
5. Add the nginx template as an NAS vhost and obtain its tailnet certificate.
   Replace `<TAILNET_IP>` in the template with the NAS tailnet IP. It must bind
   only to that address on port 443, never a public interface.
6. From a tailnet device, check `/healthz`. Pair with the TV using the CLI
   doctor command from the NAS, then carry out exactly one upload/display test.

The current web API requires `confirm=true` for upload-to-TV, display, and
rollback operations. The web server intentionally has no delete endpoint or
scheduler.
