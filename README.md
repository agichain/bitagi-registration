# CT-P5-005 registration records (CLASS_T)

```text
Status: NO PRODUCTION NETWORK ACTIVE · DO NOT ACTIVATE · Class P NO-GO · DO NOT GENESIS
Generation: D3.5 (Exact D3 Core unchanged)
```

This repository holds pre-registration records of Class T (Regtest and Signet) experiments only.
It makes no Class E or Class P claim. Nothing here approves, signs, broadcasts or funds anything.

- `CT_P5_005_REGISTRATION_V1_*.json`: the registration files. Each one has a signed annotated tag and a release.
- `pinned/<tag>/`: the exact bytes of every repository file that registration pins by SHA-256, with a `SHA256SUMS`
  list. The paths are the paths the registration names. A file pinned at another commit is under a subfolder
  that says so: `xd1-pinned-commit/`, and `policy-pending-freeze/` (the policy file as it was before its seed).
- `datasets/<tag>/`: a data file that a registration names by SHA-256, where one is posted.
- `allowed_signers`: the public half of the registration-only signing key.

The copies under `pinned/` and `datasets/` are unsigned (`UNSIGNED_MAINTAINER_SIGNATURE_REQUIRED`). The signed tag
covers the registration file, and the registration file carries the SHA-256 of each pinned file.

A post is never edited or deleted. A change is a new post.
