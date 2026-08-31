# Frame Art

`frame-art` is a deliberately small, local proof of concept for sending one
image to Art Mode on a Samsung The Frame television. It uses the
[`samsungtvws`](https://github.com/xchwarze/samsung-tv-ws-api) local WebSocket
library. It is not a hosted service, scheduler, gallery, or SmartThings client.

The interface is intentionally cautious: `doctor` only reads TV state, while
uploading and displaying each require an explicit confirmation flag. Nothing
runs in the background.

## NAS deployment

The production target is the NAS, not Kip. The service stores originals,
Frame-ready 3840×2160 JPEGs, the SQLite catalogue, audit log, and Samsung token
under one NAS-drive directory. `docker-compose.yml` exposes the application
only at `127.0.0.1:8033`; `deploy/nginx-art.kip.computer.conf` is the matching
tailnet-only NAS nginx vhost. Follow `deploy/README.md`; do not enable it until
the physical TV test is complete.

## Install

```sh
make bootstrap
```

The TV and the computer running the command must be on the same home LAN. The
first connection causes the TV to show its pairing prompt. Accept it with the
remote. The resulting token is stored in the local, ignored token file.

## Proof-of-concept sequence

1. Find the TV's LAN IP address in your router or on the TV's network page.
2. Turn on the TV and enable Art Mode. Keep the remote nearby to accept pairing.
3. Check compatibility without changing the TV:

   ```sh
   frame-art doctor --host 192.168.1.50
   ```

4. Inspect a 3840×2160 JPEG or PNG without connecting to the TV:

   ```sh
   frame-art upload artwork.jpg --host 192.168.1.50 --dry-run
   ```

5. Upload only after reviewing the preflight output. This does *not* make the
   image current:

   ```sh
   frame-art upload artwork.jpg --host 192.168.1.50 --confirm-upload
   ```

6. Copy the returned `content_id`, then make that exact image current:

   ```sh
   frame-art display MY_F0001 --host 192.168.1.50 --confirm-display
   ```

The Samsung local API is undocumented and compatibility with the 2025 model
remains the point of this experiment. If pairing, upload, or display fails, do
not automate around it; record the exact error and use it to decide the next
integration path.

## Development

```sh
make check
make test
```
