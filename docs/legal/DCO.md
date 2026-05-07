# Developer Certificate of Origin

Ome365 uses the **Developer Certificate of Origin (DCO) version 1.1** for all contributions. This replaces the heavier "Contributor License Agreement (CLA)" used by some projects.

## Why DCO over CLA

| | DCO | CLA |
|:---|:---:|:---:|
| Signing friction | Per-commit `git commit -s` | Multi-page legal doc · per-contributor |
| Corporate friction | None for individuals | Often requires legal review |
| Hyperscaler appropriation defense | None (relies on AGPLv3) | Sometimes used to grant relicensing rights |
| Linux Foundation standard | ✅ | — |
| Used by | Linux kernel · Docker · Kubernetes · Cosmos · OpenSSF | Apache · Eclipse |

DCO is signature **of origin**, not of rights transfer. You retain copyright; you certify you have the right to contribute. The pre-commit hook + GitHub DCO bot enforce this on every PR.

## DCO 1.1 Text (canonical)

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.


Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

Source: <https://developercertificate.org/>

## How to sign off

```bash
# 1. Configure your identity (one-time)
git config --global user.name "Your Name"
git config --global user.email "you@example.com"

# 2. Sign off every commit
git commit -s -m "your message"
# This appends: Signed-off-by: Your Name <you@example.com>

# 3. Or for existing commits, retroactively sign:
git rebase --signoff main
git push -f origin <your-branch>
```

## DCO and Ome365's dual-license future

Ome365 currently ships under MIT (see [`LICENSE`](../../LICENSE)). The project is migrating to **AGPLv3 (OSS main) + BSL 1.1 (Enterprise modules)** ahead of v1.1.

Your DCO sign-off authorizes inclusion of your contribution under whichever license tier is appropriate for the file at the time of relicensing. If you object to either tier, you may request your contribution be removed within 14 days of the formal license change announcement.

**This does not grant Ome365 maintainers a separate copyright license** — your sign-off only certifies origin. The AGPLv3 + BSL 1.1 dual-tier model relies on the existing OSS license terms; contributions made under MIT remain available under MIT terms forever.

## Bot enforcement

We use the [DCO GitHub App](https://github.com/apps/dco) to check every PR:

- ✅ All commits have valid `Signed-off-by:` lines → PR mergeable
- ❌ Any commit missing sign-off → PR blocked with clear instructions to fix

You can fix unsigned commits with `git rebase --signoff main` and force-push.
