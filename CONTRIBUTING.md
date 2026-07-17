# Contributing

Thank you for helping improve SurgiSabre. Contributions should preserve its
purpose as a reproducible operator-familiarisation simulation and keep the
boundary between game behaviour and clinical claims explicit.

## Before starting

Open an issue for a change that alters the control model, dependency pins,
network architecture, asset set or public interface. Small fixes and focused
test improvements can proceed directly.

Use a `feat/` branch for feature work. Keep each change scoped, reviewable and
free from generated runtimes or local evidence.

## Development setup

The pure Python state machines and validation logic can be developed without a
running simulator:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e '.[dev]'
python3 -m pytest -q
```

Isaac integration tests require the exact runtime described in `README.md` and
`docs/deployment.md`. Do not weaken a pin merely to make a local environment
appear compatible.

## Change requirements

- Add or update tests for changed behaviour.
- Update public documentation when a control, port, environment variable or
  dependency changes.
- Preserve the fixed remote-centre and clutch safety invariants.
- Treat tracking loss as a hold condition. Do not synthesise unverified poses.
- Keep scoring separate from any claim of surgical proficiency.
- Keep simulator-only evidence distinct from physical headset evidence.
- Record the exact host, headset, runtime versions and revisions for physical
  validation.

Changes to controller mapping, insertion, clutching, haptics or collision
response require both automated tests and a physical Quest acceptance run. If
physical hardware is unavailable, state that limitation clearly in the pull
request. Do not describe the change as end-to-end verified.

## Checks

Run these checks before submitting a change:

```bash
python3 -m ruff check src tests
python3 -m pytest -q
bash -n scripts/*.sh
git diff --check
```

For shell or deployment changes, also run the capacity preflight and a clean
start-stop cycle on the supported host. For scene or rendering changes, inspect
the result in a physical headset where possible.

## Dependency and asset policy

Do not commit:

- Isaac Sim or Kit binaries
- CloudXR archives, libraries, npm packages or generated bundles
- IsaacTeleop wheels containing CloudXR binaries
- i4h USD or mesh payloads
- private certificates, keys, tokens or host configuration
- logs, telemetry, recordings or evidence with personal identifiers
- proprietary branding, fonts or internal-use artwork

New assets require an immutable source identity, SHA-256 digest, clear licence
and an entry in `ASSET_MANIFEST.md`. New third-party code requires its licence
text and notice in `THIRD_PARTY_NOTICES.md` before merge.

Retain upstream copyright and SPDX headers. Mark modified upstream files or
patches clearly. Do not use an upstream project or contributor name to imply
endorsement.

## Pull request description

Include:

- the practical operator-facing change
- changed files and intentionally untouched areas
- automated checks and their results
- simulator runtime evidence, if applicable
- physical Quest evidence, if applicable
- new security, licence or deployment implications

## Conduct

Be precise, constructive and respectful. Discuss behaviour and evidence rather
than people. Safety concerns and contradictory runtime evidence should be
raised directly and treated as release blockers until resolved.

## Contribution licence

By submitting a contribution, you agree that it may be distributed under the
repository's Apache License 2.0 and that you have the right to provide it under
those terms.

