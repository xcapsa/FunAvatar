#!/usr/bin/env python3
"""Inspect VRChat avatar OSC configs and prepare typed plans; never send traffic.

Protocol and configuration sources (no third-party implementation copied):
https://docs.vrchat.com/docs/osc-avatar-parameters
https://docs.vrchat.com/docs/osc-overview
https://creators.vrchat.com/avatars/animator-parameters/
https://opensoundcontrol.stanford.edu/spec-1_0.html
"""

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import sys


MAX_CONFIG_BYTES = 4 * 1024 * 1024
MAX_PARAMETERS = 16384
MAX_NAME_BYTES = 256
MAX_ADDRESS_BYTES = 1024
MAX_PATH_BYTES = 4096
AVATAR_ID = re.compile(r"avtr_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
TYPES = {"Bool", "Int", "Float"}
# VRChat's built-in and avatar-scaling parameter tables: all are read-only.
READ_ONLY = frozenset("""
IsLocal PreviewMode Viseme Voice GestureLeft GestureRight GestureLeftWeight
GestureRightWeight AngularY VelocityX VelocityY VelocityZ VelocityMagnitude
Upright Grounded Seated AFK TrackingType VRMode MuteSelf InStation Earmuffs
IsOnFriendsList AvatarVersion IsAnimatorEnabled ScaleModified ScaleFactor
ScaleFactorInverse EyeHeightAsMeters EyeHeightAsPercent
""".split())


class OSCPlanError(ValueError):
    pass


def _text(value, label, limit):
    if not isinstance(value, str) or not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise OSCPlanError(f"Invalid {label}")
    try:
        size = len(value.encode("utf-8"))
    except UnicodeError:
        raise OSCPlanError(f"Invalid {label}") from None
    if size > limit:
        raise OSCPlanError(f"{label} is too long")
    return value


def _path(value):
    path = Path(value).expanduser().absolute()
    if len(os.fsencode(path)) > MAX_PATH_BYTES:
        raise OSCPlanError("Path is too long")
    return path


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise OSCPlanError("Duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_):
    raise OSCPlanError("Nonfinite JSON value")


def _json(raw):
    try:
        return json.loads(raw, object_pairs_hook=_pairs, parse_constant=_nonfinite)
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        raise OSCPlanError("Invalid bounded JSON") from None


def _endpoint(value, direction):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise OSCPlanError("Invalid OSC endpoint")
    address = _text(value.get("address"), "OSC address", MAX_ADDRESS_BYTES)
    allowed = TYPES | ({"bool"} if direction == "output" else set())
    if not isinstance(value.get("type"), str) or value["type"] not in allowed:
        raise OSCPlanError("OSC endpoint type must be Int, Bool or Float")
    return {"address": address, "type": value["type"]}


def load_config(filename):
    path = _path(filename)
    if path.is_symlink():
        raise OSCPlanError("Config must not be a symlink")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_CONFIG_BYTES:
            raise OSCPlanError("Config must be a bounded regular file")
        raw = stream.read(MAX_CONFIG_BYTES + 1)
    if len(raw) > MAX_CONFIG_BYTES:
        raise OSCPlanError("Config exceeds size limit")
    config = _json(raw)
    if not isinstance(config, dict) or not isinstance(config.get("id"), str) or not AVATAR_ID.fullmatch(config["id"]):
        raise OSCPlanError("Config needs a canonical avtr UUID")
    name = _text(config.get("name"), "avatar name", 1024)
    parameters = config.get("parameters")
    if not isinstance(parameters, list) or len(parameters) > MAX_PARAMETERS:
        raise OSCPlanError("Config needs a bounded parameters array")
    filename_id = path.stem if AVATAR_ID.fullmatch(path.stem) else None
    if filename_id is not None and filename_id != config["id"]:
        raise OSCPlanError("Config filename avatar ID does not match its contents")
    validated, seen, input_addresses = [], set(), set()
    for parameter in parameters:
        if not isinstance(parameter, dict):
            raise OSCPlanError("Invalid parameter record")
        parameter_name = _text(parameter.get("name"), "parameter name", MAX_NAME_BYTES)
        if parameter_name in seen:
            raise OSCPlanError("Duplicate parameter name")
        seen.add(parameter_name)
        incoming = _endpoint(parameter.get("input"), "input")
        if incoming is not None:
            if incoming["address"] in input_addresses:
                raise OSCPlanError("Duplicate OSC input address requires review")
            input_addresses.add(incoming["address"])
        validated.append({"name": parameter_name, "input": incoming,
                          "output": _endpoint(parameter.get("output"), "output")})
    evidence = {"path": str(path.resolve()), "sha256": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw), "avatar_id": config["id"], "avatar_name": name,
                "filename_avatar_id": filename_id}
    return evidence, validated


def _restriction(parameter):
    if parameter["name"] in READ_ONLY:
        return "builtin_read_only"
    endpoint = parameter["input"]
    if endpoint is None:
        return "no_input"
    address = endpoint["address"]
    if address != "/avatar/parameters/" + parameter["name"]:
        return "nonstandard_input_requires_review"
    # Keep names exact. Spaces, Unicode and OSC wildcard patterns need review,
    # not renaming or escaping that would target a different parameter.
    if (any(ord(char) > 126 or char in " #*,?[]{}" for char in address)
            or any(part in ("", ".", "..") for part in address.split("/")[1:])):
        return "nonstandard_input_requires_review"
    return None


def _base(kind, evidence):
    return {"schema_version": 1, "kind": kind, "mode": "plan_only",
            "sent": False, "runtime_verified": False, "config": evidence}


def inspect_config(filename):
    evidence, parameters = load_config(filename)
    result = _base("funavatar_osc_avatar_config", evidence)
    result.update(writable_inputs=[], outputs=[], blocked_inputs=[])
    for parameter in parameters:
        reason = _restriction(parameter)
        if reason is None:
            result["writable_inputs"].append({"name": parameter["name"], **parameter["input"]})
        else:
            result["blocked_inputs"].append({"name": parameter["name"], "reason": reason,
                                             "input": parameter["input"]})
        if parameter["output"] is not None:
            result["outputs"].append({"name": parameter["name"], **parameter["output"]})
    result["limitation"] = "Config-declared inputs only; active avatar, OSC enablement and effects were not observed."
    return result


def _osc_string(value):
    raw = value.encode("ascii") + b"\0"
    return raw + b"\0" * (-len(raw) % 4)


def _message(address, kind, value):
    if kind == "Bool":
        if type(value) is not bool:
            raise OSCPlanError("Bool values must be JSON true or false")
        tag, payload, encoded = ("T" if value else "F"), b"", value
    elif kind == "Int":
        if type(value) is not int or not -(2 ** 31) <= value < 2 ** 31:
            raise OSCPlanError("Int values must be signed int32 JSON integers, not booleans")
        tag, payload, encoded = "i", struct.pack(">i", value), value
    elif kind == "Float":
        if type(value) not in (int, float):
            raise OSCPlanError("Float values must be finite JSON numbers, not booleans")
        try:
            number = float(value)
            if not math.isfinite(number):
                raise ValueError
            payload = struct.pack(">f", number)
        except (OverflowError, ValueError, struct.error):
            raise OSCPlanError("Float value is not representable as finite float32") from None
        tag, encoded = "f", struct.unpack(">f", payload)[0]
    else:
        raise OSCPlanError("Unsupported OSC input type")
    packet = _osc_string(address) + _osc_string("," + tag) + payload
    return {"address": address, "type_tag": "," + tag, "encoded_value": encoded,
            "packet_hex": packet.hex(), "byte_length": len(packet)}


def plan(filename, avatar, parameter, value, reset):
    evidence, parameters = load_config(filename)
    if not isinstance(avatar, str) or not AVATAR_ID.fullmatch(avatar) or avatar != evidence["avatar_id"]:
        raise OSCPlanError("Requested avatar ID does not match config")
    selected = next((item for item in parameters if item["name"] == parameter), None)
    if selected is None:
        raise OSCPlanError("Exact parameter name is absent from config")
    restriction = _restriction(selected)
    if restriction is not None:
        raise OSCPlanError("Parameter cannot be planned: " + restriction)
    endpoint = selected["input"]
    steps = [{"action": action, "value": item, "sent": False,
              "osc": _message(endpoint["address"], endpoint["type"], item)}
             for action, item in (("set", value), ("reset", reset))]
    result = _base("funavatar_osc_avatar_plan", evidence)
    result.update(avatar_id=avatar, avatar_id_matches_config=True,
                  active_client_avatar_verified=False, parameter=selected, steps=steps,
                  port_defaults={"vrchat_receives": 9000, "vrchat_sends": 9001,
                                 "configurable": True, "observed": False},
                  limits=["Plan only: no transport, sockets, listener or client observation.",
                          "Input type bounds are OSC wire bounds, not proof of animator range or synchronization.",
                          "Reset is user-supplied; the current or original value was not read.",
                          "Before any later external execution, verify the active avatar and config hash again."])
    return result


def _value(raw):
    if len(raw.encode("utf-8")) > 256:
        raise OSCPlanError("Value JSON is too long")
    return _json(raw)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect_parser = commands.add_parser("inspect", help="List config-declared inputs and outputs, without network access")
    inspect_parser.add_argument("config")
    plan_parser = commands.add_parser("plan", help="Prepare a set/reset packet plan; never send it")
    plan_parser.add_argument("config")
    plan_parser.add_argument("--avatar", required=True)
    plan_parser.add_argument("--parameter", required=True)
    plan_parser.add_argument("--value", required=True, help="JSON scalar matching the config input type")
    plan_parser.add_argument("--reset", required=True, help="Explicit JSON reset value of the same input type")
    plan_parser.add_argument("--out", help="Create a new JSON plan file; existing files are never overwritten")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_config(args.config)
        else:
            result = plan(args.config, args.avatar, args.parameter, _value(args.value), _value(args.reset))
        rendered = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.command == "plan" and args.out:
            with _path(args.out).open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        print(rendered, end="")
        return 0
    except (OSError, ValueError) as error:
        print(f"funavatar-osc: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
