# Security policy

SurgiSabre joins an XR browser, a streaming runtime and a GPU simulator across
a network. Treat every deployment as a service boundary, even when it runs on
a private laboratory network.

## Reporting a vulnerability

Use GitHub private vulnerability reporting through this repository's Security
tab. Do not open a public issue for a suspected vulnerability, leaked secret or
working exploit.

Include the affected revision, deployment topology, reproduction steps,
observed impact and any safe mitigation already tested. Remove credentials,
private keys, patient information, personal identifiers and private network
addresses from the report unless the private reporting channel specifically
requires them.

There is no guaranteed response time. Maintainers will acknowledge and assess
reports as capacity permits, prioritising credential exposure, remote access,
unsafe controller behaviour and dependency compromise.

## Supported versions

Until versioned releases are published, only the current default branch is
supported. Historical commits and locally modified dependency stacks may still
be useful for research, but they do not receive security fixes unless the issue
also affects the current branch.

## Network boundary

The validated CloudXR configuration uses a direct route or private network
overlay. It has no SurgiSabre authentication layer and is not designed for
anonymous Internet clients. The current direct-media path does not provide a
general ICE or TURN deployment.

- Restrict TCP and UDP ingress to the intended operator network.
- Use a hostname and TLS certificate trusted by the Quest browser.
- Do not bind management or development services to a public interface.
- Do not publish a client URL containing a private token or internal hostname.
- Stop the service when it is not under active supervision.
- Review NVIDIA CloudXR guidance before changing transport security.

Do not describe a deployment as safely Internet-facing without an explicit
threat model, authentication, origin restrictions, rate controls and a reviewed
ICE or TURN design.

## Secret handling

Never commit `.env` files, certificates, private keys, tokens, SDK credentials,
tailnet identities or session evidence. Use project-scoped data directories
outside the repository and limit their permissions. Rotate a credential if it
appears in a log, shell history, issue, commit or generated archive.

The repository ignores common key and certificate formats, but ignore rules are
not a security control. Run a secret scan before every public release.

## Runtime safety

Tracking loss, invalid poses and controller disconnects must hold the last safe
tool target and require deliberate clutch re-engagement. Report any behaviour
that causes an uncontrolled jump, persistent motion after disengagement or
unexpected connection from another client as a security and safety issue.

On unified-memory hosts, resource exhaustion can terminate both simulation and
streaming. Monitor free memory throughout large builds and runtime sessions.
Avoid concurrent heavyweight work and stop the project-owned process cleanly
before the host reaches dangerous memory pressure.

## Non-clinical boundary

SurgiSabre is not a medical device, patient-care system or clinical training
certification. Do not connect it to a physical surgical robot or a patient.
Reports involving clinical use will be treated as unsupported and potentially
unsafe deployment.

