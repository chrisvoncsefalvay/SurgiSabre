# Architecture

SurgiSabre is a project-scoped application layer. It does not fork the entire
Isaac Sim, Isaac Lab or IsaacTeleop runtime.

```text
Quest tracking and triggers
  -> CloudXR 6.2.0 and OpenXR
  -> IsaacTeleop motion controller device
  -> SurgiSabre clutched absolute hinged retargeting
  -> Isaac Lab dVRK PSM action terms
  -> Isaac Sim and PhysX

PSM contact sensors
  -> target lifecycle and impulse response
  -> gravity release, haptic request, score update and side-light event
  -> session JSONL telemetry
```

## Control contract

Each controller owns one PSM. Orientation is interpreted absolutely within a
clutch interval, but the tool remains hinged around its remote centre. Motion
along the controller's current tool axis changes insertion. Releasing the
clutch freezes the commanded pose. Re-engagement registers a new controller
reference without intentionally moving the instrument.

This is deliberately different from pretending that a Quest controller is an
MTM. The application exposes that translation so operators can learn it in a
low-stakes environment.

## Course contract

Six project-authored rigid targets approach in two lanes. Their colour, height
and speed are deterministically randomised from the session identifier. A target
has gravity disabled while approaching. The first valid distal-instrument hit
enables gravity, applies an impulse-like velocity and emits one haptic request.
A missed target is counted once before recycling.

The base Isaac Lab task identifier still contains `NeedlePass`, but the
SurgiSabre layout removes the needle, suture pad, needle contact sensors and RL
termination layer. Trigger-driven jaw motion remains available while jaw
collision and gripping physics remain disabled.

## Presentation contract

The arena uses a dark dome, a plain white table, a side-mounted score panel and
two event-reactive side lights. No external logo, font or environment texture
is required. Scene changes are event-driven rather than authored every frame.
