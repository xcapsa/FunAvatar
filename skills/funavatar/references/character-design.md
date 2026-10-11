# Character foundations, expression and broad usability

Use this reference for character strategy, researching distinctive VRChat avatars, planning animation and signature features, or interpreting “universal.” Use the existing concept, production and debug routes for actual assets. A feature plan is not an implemented avatar.

## Research without inventing a popularity ranking

Study original creator pages and demonstrations. Attribute documented capabilities to the creator, distinguish shipped assets from add-ons and proposals, and label design lessons as interpretation. Historical product setup instructions are not current VRChat SDK guidance. Do not infer sales, active users, compatibility or “most popular” status from visibility or a marketplace listing.

Use a few contrasting references for a specific question: facial expression, silhouette, customization, social interaction or transformation. Extract principles instead of copying a character's identity. A striking showcase does not prove ordinary multiplayer performance.

Creator examples checked on 2026-10-11; the lessons below are design interpretations, not a ranking or a claim that these assets were tested. Recheck current listings before quoting capabilities, availability or licensing.

| Example | Documented reference point | Design lesson |
| --- | --- | --- |
| [Manuka — STUDIO JINGO](https://jingo1016.booth.pm/items/5058077) | Numerous facial shape keys, facial animations and appearance customization | Invest in the face and a recognizable expression language before decorative effects. |
| [Rexouium — Rezillo Ryker](https://rezilloryker.gumroad.com/l/MYutV) | Controls and expressions for ears, tail, mouth, tongue and toes | Distinctive anatomy can communicate personality through movement. |
| [Nardoragon — Nardo](https://jinxxy.com/Nardo/Nardoragon) | Secondary motion, face tracking support, headpat/boop reactions and a separate Quest version | Social interactions can be memorable features that fit the character. |
| [Deltaflair — VERMILION Studio](https://kv2.booth.pm/items/4906631) | Separate PC/Quest distributions with explicitly reduced features on Quest | Broad availability needs planned adaptations and honest feature differences. |

## Define the character before the feature inventory

Record the smallest brief that makes decisions possible:

- Identity: name, species/archetype, personality and intended social use.
- Recognition: silhouette, proportions, face/head shape, palette/material hierarchy and one or two identifying details. Check that the design remains readable without glow, particles or elaborate lighting.
- Expression: how eyes, brows, mouth, hands and species-specific parts communicate the character's emotions. Choose the face or helmet mechanism deliberately.
- Variation: which identity cues stay fixed across outfits, colors, body options and transformations, and which may change.
- Signature behavior: a distinctive interaction or transformation that fits this character, plus supporting features when useful.
- Delivery: target platforms, available controls/tracking, intended performance target and whether this is a personal character or a reusable base for others.

An expressive base should still feel complete while standing, talking, sitting and greeting someone with special effects disabled. Technical breadth does not replace a recognizable character.

## Build expression in layers

| Layer | Design goal | Implementation considerations |
| --- | --- | --- |
| Body and hands | Convincing posture, movement and gestures | Suitable rig, skin weights and deformation topology; check seated poses, shoulders, elbows, wrists, hips and knees. Use a humanoid rig when that serves tracking/retargeting; unusual anatomy may require a deliberate generic rig and tradeoffs. |
| Face and speech | Readable emotion during conversation | Visemes/lip sync, blinking, eye movement and intentional facial expressions. Simulated eye movement is different from hardware eye tracking. Avoid smiles, blinking and speech deforming the same area incompatibly. |
| Secondary motion | Hair, ears, tail and clothing react naturally | PhysBones and suitable colliders/limits where supported. Damping and range should suit anatomy; more moving bones do not automatically improve the result. |
| Social reactions | Other people can understand and interact with the character | Contacts can drive bounded responses such as a headpat reaction or nose boop. Account for self/others permissions, interaction settings, range, cooldown and a way to disable the response. |
| Signature feature | A memorable action tied to identity | For example, a robot's deployable tool, a creature's emotional tail/ear system, or a magical character's alternate form. Specify trigger, transitions, response, reset and a lighter alternative. |
| Optional tracking | Richer behavior with suitable hardware/software | Verify the actual supported face/eye/body tracking route and installed versions. Preserve usable gesture/menu/automatic behavior without that equipment; distinguish announced or beta functionality from released support. |

Plan which system owns each animated property. Tracking, gesture expressions, lip sync, blinking, contact responses and manual overrides need clear precedence and return-to-neutral behavior. For a transformation, define valid entry/exit states and shared identity; major anatomy changes can require separate meshes or rigs rather than one morph.

“Animated to the maximum” should mean responsive and expressive across normal use, with stable transitions. Constant movement and dense effects can obscure the character or become tiring.

## Make “universal” measurable

Resolve the intended scope from the request. Distinguish device/platform coverage, input/tracking coverage, visual customization and reuse outside VRChat. If another app is requested, treat its rig, materials, format and feature support as a separate export/validation target; a VRChat package alone does not prove portability.

For VRChat, plan a shared identity with platform-specific builds as needed. PC, native Android/Quest and native iOS have different capabilities or restrictions. Quest connected to a PC uses the PC client; it is not evidence for the native Quest build. Do not assume an Android test certifies iOS.

The project-check/debug-plan tools and 3D ledger use `pc`, `android` and `both`, where `both` means PC plus Android only. The separate [numeric budget checker](performance-budgets.md) can apply the shared mobile profile to `ios`, and a native report can record an iOS target; neither adds an iOS SDK/client gate to the ledger. Retain requested iOS support in the avatar contract and record its SDK/client/device evidence separately; do not relabel it as Android or mark it passed through a `both` check.

Use a compact matrix for the actual targets:

| Feature | Target/platform | Input or hardware | Full, simplified or unavailable | Validation/evidence |
| --- | --- | --- | --- | --- |
| Core face, voice and gestures | Each requested target | Ordinary controls | Planned behavior | Not implemented/tested until observed |
| Signature feature | Each requested target | Menu/gesture/contact | Explicit alternative if needed | Local, remote and device result separately |
| Optional tracking | Supported target | Named equipment/software | Usable fallback without tracking | Actual setup and client test |

Preserve silhouette, face, main palette and a recognizable signature cue in lighter builds. Simplify mesh/materials, textures, physics and effects for the target rather than promising identical visuals. Use current supported shaders/components and verify per-platform overrides and parameter compatibility when sharing an avatar identity across builds.

Performance is a design budget from the beginning. Track the installed SDK's relevant metrics, including texture memory, materials, renderers, bones, physics, contacts, constraints and effects. Hidden or disabled objects can still count toward rank; a menu toggle is not proof of optimization. Performance rank is a useful static signal, not a frame-rate guarantee. Test normal social use as well as the showcase configuration.

## Keep many features usable

Organize controls around the person wearing the avatar: expression, appearance, interaction and special actions as appropriate. Use clear names, sensible defaults, reset controls and quick access to frequent actions. A recommended daily-use mode can reduce visual/audio activity; only an actually optimized build establishes a lighter static asset cost.

For each nontrivial feature, record purpose, trigger, required assets, animated properties, parameters, local/remote visibility, persistence, compatible states, platform alternatives and test status. Synchronize what other people need to see; distinguish local settings from synchronized behavior. Check the current parameter budget and network behavior rather than assuming every continuously animated value can be shared at full precision.

Use supported avatar components and animation systems. Arbitrary Unity scripts and world Udon logic are not an unrestricted scripting mechanism for worn avatars. Prefer existing working native components before adding dependencies. Add-ons must have compatible versions and licenses; buying a base does not imply redistribution rights for its assets.

If the user wants a reusable commercial/community base, also plan clean source files, stable naming, documented material/rig conventions, outfit/accessory attachment points, customization options and clear license terms. The existence of these facilities is separate from whether a surrounding creator ecosystem actually exists.

## Implementation stages and meaningful evidence

Adapt the sequence to existing assets; do not restart a working avatar merely to follow this list.

1. Set the brief, targets, identity invariants and signature behavior. Mark optional ideas separately from required features.
2. Approve one master design and consistent modeling views. Keep a small behavior sheet showing key expressions or transformations.
3. Build or repair geometry, deformation topology, UVs and textures. For generated 3D, apply the [reference fidelity gate](technical-handoff.md#image-to-3d-fidelity-gate) before rigging/effects.
4. Validate rig, weights, proportions and ordinary movement. Establish voice, face and gesture behavior before stacking interactions.
5. Implement secondary motion and signature features with property ownership, state transitions, parameters and resets defined.
6. Produce the target-specific versions and useful control fallbacks. Measure the actual imported/built assets against current budgets.
7. Check SDK validation, then test in client. Separate self/mirror, another client's view, late joining, avatar reload, feature combinations, safety/interaction settings and each actual target device. A local Build & Test avatar is visible only to its wearer, so it cannot establish remote synchronization.
8. Record the tested revision, known limitations and next action in that avatar's project brief. Upload/publication still requires the user's scope for that external action.

## Current primary guidance

Official pages checked on 2026-10-11. Recheck at implementation time, especially numerical limits, supported versions and new tracking/network capabilities. These links provide guidance, not evidence that a specific avatar passed testing.

- [Avatars](https://creators.vrchat.com/avatars/): facial basics, humanoid/generic distinctions and local test visibility.
- [Playable Layers](https://creators.vrchat.com/avatars/playable-layers/): animation responsibilities and masks.
- [PhysBones](https://creators.vrchat.com/common-components/physbones/) and [Contacts](https://creators.vrchat.com/common-components/contacts/): secondary motion and interaction.
- [Expressions Menu and Controls](https://creators.vrchat.com/avatars/expression-menu-and-controls/) and [Animator Parameters](https://creators.vrchat.com/avatars/animator-parameters/): wearer controls, synchronization and tracking inputs.
- [Performance Ranks](https://creators.vrchat.com/avatars/avatar-performance-ranking-system/) and [Avatar Optimization Tips](https://creators.vrchat.com/avatars/avatar-optimizing-tips/): static metrics and practical optimization.
- [Cross-Platform Setup](https://creators.vrchat.com/platforms/android/cross-platform-setup/), [Per-Platform Avatar Overrides](https://creators.vrchat.com/avatars/per-platform-avatar-overrides/), [Android Content Limitations](https://creators.vrchat.com/platforms/android/quest-content-limitations/) and [iOS](https://creators.vrchat.com/platforms/iOS/): target-specific planning and shared mobile guidance.
- [Allowed Avatar Components](https://creators.vrchat.com/avatars/avatar-components/): supported component boundary.
- [Projects and chats](https://learn.chatgpt.com/docs/projects): shared project context and focused chats; the one-primary-chat-per-avatar convention is the user's FunAvatar preference.
