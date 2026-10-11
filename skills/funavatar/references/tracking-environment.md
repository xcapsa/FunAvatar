# Tracking, complete animation and environment response

Use for a character that must move with its wearer, animate fully, and have responsive clothing. Deliver an actual skinned character matching the approved design, with the intended limb/digit anatomy and deforming garments where present; a static mesh, posed render, cube mannequin or component inventory cannot satisfy that request.

Keep three systems separate: **rig/skinning**, **input/IK and animation**, and **secondary physics/environment response**. Inspect an existing implementation before replacing it. The sources below were checked on 2026-10-11; recheck installed SDK behavior and current guidance at implementation time.

## Rig and real tracking input

For a humanoid-compatible character and input route, inspect Unity Humanoid mapping, bind/T-pose, scale and weights on the final imported mesh. For quadrupeds or other anatomy, preserve the reference and define the target-supported rig and wearer-input mapping explicitly; do not reshape the character or add fingers just to fit a humanoid default. Map the intended optional bones as well as required bones; a valid auto-map does not establish correct deformation. Inspect both hands' actual finger mapping, then preview opening, closing and splay with suitable muscle ranges. [Unity Humanoid import](https://docs.unity3d.com/2022.3/Documentation/Manual/ConfiguringtheAvatar.html) explains mapping; [VRChat Skeletal Input](https://docs.vrchat.com/docs/steamvr-input-20) explains finger-muscle tuning.

Finger bones do not supply tracking data. Distinguish controller-generated/estimated finger poses, hardware skeletal finger data, and actual controller-free hand tracking. SteamVR full hand tracking needs compatible hardware and a supplying driver; its Input 2.0 route does not apply to native Quest. Preserve gesture/menu fallbacks and record the exact headset, controllers/cameras/gloves, driver, client and settings actually tested.

FBT needs available tracker data, an appropriate rig and calibration, including height, floor/playspace and alignment. Record the actual tracked points and missing-data fallback. Consult [FBT calibration](https://docs.vrchat.com/docs/full-body-tracking) alongside [OSC Trackers](https://docs.vrchat.com/docs/osc-trackers): the former's exclusive Lighthouse wording conflicts with the latter's explicit OSC support. Do not repeat that exclusivity or treat OSC as plug-and-play. A rig cannot manufacture absent trackers; mobile FBT support for an unspecified setup remains unestablished.

## A complete, interruptible animation set

Specify coverage for idle, walk/run, turn, sit, crouch, gestures/fingers, speech/face and required prop actions. Identify whether each behavior uses existing locomotion/IK, an authored clip or a fallback; do not invent existing clips. Deliver the required actions/clips, controller states, masks, transitions and resets.

Assign one owner per property. [Animator Tracking Control](https://creators.vrchat.com/avatars/state-behaviors/) switches body parts between Tracking and Animation; its setting persists until explicitly changed. `No Change` is not a reset. Every override needs an exit/interruption path restoring intended tracking, layer weights, locomotion and facial systems. Test seated/crouched entry and exit, interrupted gestures/props, retriggering and avatar reload without stuck limbs or fingers.

## Clothing, gravity, wind and water

Garments must first follow body motion through skin weights or an appropriate attachment. A Blender/offline cloth bake and a standalone Unity cloth/environment simulation are separate deliverables and validation targets; neither proves live VRChat behavior.

For supported secondary motion, [PhysBones](https://creators.vrchat.com/common-components/physbones/) provide bone-chain pull, spring/momentum, gravity, motion damping, limits and selected/global PhysBone colliders. Tune only the intended hair, straps, skirt or other secondary chains; test fast stops and settling. They are not a general cloth/fluid solver. Do not put their roots on Humanoid bones, let a Constraint and PhysBone control the same object, or apply whole-body gravity that collapses the tracked character. Do not assume ordinary world geometry supplies compatible collision. Avatar PhysBone force properties are initialized constants; animating them with off/on toggles is explicitly unsupported.

Universal automatic `WindZone`, water detection, buoyancy or drag for worn avatars is **not established**. Do not invent a world-detection API. A cooperating world can use a [Contact Sender](https://creators.vrchat.com/common-components/contacts/) configured for avatar content and matching case-sensitive tags; an avatar Contact Receiver can set its Animator parameter. Proposed tags such as `FunAvatarWater` are a custom agreement, not built-in weather semantics. Use that signal for an authored motion/material response, with permissions, exit/reset and remote tests. This does not create physical water forces. Provide a wearer-controlled mode when world cooperation is absent.

Use the [allowed component list](https://creators.vrchat.com/avatars/whitelisted-avatar-components/whitelisted-avatar-components/) for PC: it includes Cloth but excludes arbitrary custom scripts. [Android limitations](https://creators.vrchat.com/platforms/android/quest-content-limitations/) disable avatar Cloth, standard rigidbodies/colliders/joints and Unity constraints; use supported VRChat Constraints where appropriate. [iOS guidance](https://creators.vrchat.com/platforms/iOS/) applies the Android/Quest guidance too. Verify target budgets and build/device behavior separately.

## Acceptance and concrete delivery

Start each applicable row at `not_verified`; record failures and unavailable inputs explicitly.

| Required feature | Input / platform | Evidence to pass | Initial status |
| --- | --- | --- | --- |
| Body and clothing deformation | Ordinary controls; each requested PC/mobile target | Turn, arms raised, lean, walk/stop, sit/crouch; native rig and client recording | `not_verified` |
| Animation, face and props | Defined triggers on each target | Covered state set; speech/expressions, transitions, interruption, retrigger and tracking/reset restoration | `not_verified` |
| Fingers and hand tracking | Named controller/skeletal/hand-tracking route | Both hands open/close/splay; tracking on/off and gesture interruption/restoration | `not_verified` |
| FBT | Named trackers and client route | Calibration, feet/hips/torso motion, loss/recovery and animation override exit | `not_verified` |
| Secondary gravity/motion | Supported chains on each target | Motion, collision/limits, settling, reset; no body collapse | `not_verified` |
| Wind/water response | Cooperating world plus manual fallback | Enter/exit, no-signal fallback, reset and another client's view | `not_verified` |

Deliver editable `.blend` mesh/armature/weights/actions and the Unity avatar prefab/project or package with actual clips/controllers, materials and supported dynamics. Tie build logs and local, mirror, remote-client and native Android/iOS results to the exact revision. Unrun device tests remain unverified; static art cannot certify animation, tracking or environmental physics.
