# OSC inspection and controlled runtime work

Start with the exact avatar and client configuration. The bundled `scripts/osc_avatar.py` is an **offline planner**: it reads an explicit config, validates input types and encodes set/reset packets. It imports no networking library, binds no port and sends nothing. It is not a running MCP bridge, avatar controller or client-identity probe.

```sh
python3 scripts/osc_avatar.py inspect avatar-config.json
python3 scripts/osc_avatar.py plan avatar-config.json --avatar avtr_00000000-0000-0000-0000-000000000001 --parameter FaceMode --value '2' --reset '0' --out new-face-mode-plan.json
```

Replace the example identifier with the ID from the actual selected config and intended avatar. The planner checks that ID, the config hash, filename identity when present, unique parameter names/addresses, writable input, type and mandatory reset. It accepts literal avatar-parameter addresses only. Output-only, built-in read-only, nonstandard, ambiguous or pattern-based controls require inspection rather than silent renaming or packet generation. Wire int32/float32 bounds do not establish the Animator's meaningful range or synchronized parameter type.

The plan records packet bytes and a reset separately, with `sent: false`, `runtime_verified: false` and `active_client_avatar_verified: false`. Those fields must remain false after planning. A config file proves neither which avatar is currently worn nor whether the receiver applied a packet.

## Discover the real client before runtime execution

VRChat normally receives OSC on port 9000 and sends on 9001, but launch options can change them. Inspect the real setup; do not start a second listener that steals another app's receiver port. A local `/avatar/change` observation can identify an avatar change. Configs are generated for published avatars; local Build & Test does not save the same config files, so absence there is not proof of a broken avatar. [OSC overview](https://docs.vrchat.com/docs/osc-overview), [avatar parameters and config format](https://docs.vrchat.com/docs/osc-avatar-parameters).

If the user requests actual runtime control and an authorized existing OSC/MCP tool is available:

1. Verify the active avatar ID, client, configured ports and the selected parameter's real input mapping. Keep the session bounded and invalidate it after an avatar change.
2. Record the starting value, intended value/range, reset and observation needed to judge the result. Use one parameter and one hypothesis first.
3. Send through the available connector only within that authorized scope. Apply a bounded rate and avoid loops that can outlive the task.
4. Observe the resulting state in the actual client, then reset and verify recovery. Keep local, remote-client and target-device results separate.

Do not send `Voice` to manufacture speech: it is a built-in read-only microphone-volume value. A display driven by speech uses that native value in its animation logic; a custom face-mode toggle is a different parameter. [Animator parameter contract](https://creators.vrchat.com/avatars/animator-parameters/).

Chatbox messages, microphone/audio routing, motion control and autonomous social behavior are separate actions, not a side effect of discovery. Do not start connectors that send a greeting automatically. Reuse the user's existing authorization where applicable; otherwise prepare the exact action before requesting the missing scope. Keep authentication, voice data and conversation contents out of shared logs and model handoffs.

The inspected Krekun OSC implementation has commercial-use restrictions and an automatic chatbox message at startup. FunAvatar's planner is an independent implementation of the documented OSC format; no Krekun code is bundled. Consult [the capability registry](../assets/mcp-capability-registry.json) before choosing an external bridge, then inspect its current version and actual exposed tools.
