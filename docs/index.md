# Frame Art

Frame Art is a cautious, local proof of concept for uploading a single image to
Art Mode on a Samsung The Frame television using `samsungtvws`.

Its three commands are deliberately narrow:

- `doctor` verifies connectivity and reads TV state without changing it.
- `upload` runs image preflight first and requires `--confirm-upload`.
- `display` requires `--confirm-display` before it changes the current art.

The full pairing checklist and command examples are in the project README.
