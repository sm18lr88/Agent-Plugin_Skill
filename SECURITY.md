# Security Policy

## Supported releases

Security fixes apply to the latest published release. Older releases can remain unsupported.

## Report a vulnerability

Use a private GitHub security advisory for `sm18lr88/Agent-Plugin_Skill` after the repository exists.

Include:

- the affected file and function.
- attacker capability and required conditions.
- a safe proof or reproduction procedure.
- observed impact.
- the smallest known correction.

Do not include live credentials or private user data.

## Scope

Security-sensitive areas include package paths, symlinks, archive output, subprocess use, secret detection, and upstream source pins.

The validator does not sandbox plugins or establish package trust. Agent Plugins 1.0.0 does not define signing, trust roots, or portable secret storage.
