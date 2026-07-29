# Non-author public-access test protocol

Run this after the repository is intentionally made public.

1. Use a device/browser or GitHub account that is not an author account.
2. Open the public repository URL without an author login.
3. Download the repository archive or run `git clone` using the public URL.
4. Record the date, account type and public URL.
5. Run `python3 validate_public_release.py` from the repository root.
6. Save complete stdout/stderr and compute the downloaded archive/commit hash where applicable.
7. Confirm the validator reports PASS and that no permission, missing-file or dependency error occurred.

Record the test result in the release audit log and preserve the tested commit and tag.
