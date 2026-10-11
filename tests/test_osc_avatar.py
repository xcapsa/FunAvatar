"""Offline OSC config and wire-format checks; no client/runtime claims."""

import ast
from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import importlib.util
import io
import json
import math
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import urllib.request


SCRIPT = Path(__file__).resolve().parents[1] / "skills/funavatar/scripts/osc_avatar.py"
SPEC = importlib.util.spec_from_file_location("osc_avatar", SCRIPT)
osc = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(osc)
AVATAR = "avtr_11111111-2222-4333-8444-555555555555"
OTHER = "avtr_aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"


def entry(name, kind="Int", *, input_address=None, output=True):
    result = {"name": name, "input": {"address": input_address or "/avatar/parameters/" + name, "type": kind}}
    if output:
        result["output"] = {"address": "/avatar/parameters/" + name, "type": kind}
    return result


class OSCAvatarTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.path = self.root / (AVATAR + ".json")
        self.config = {"id": AVATAR, "name": "Test avatar", "parameters": [entry("FaceMode")]}
        self.write()
        for target in ("socket.socket", "socket.create_connection", "socket.getaddrinfo", "urllib.request.urlopen"):
            guard = patch(target, side_effect=AssertionError("OSC helper must never use networking"))
            guard.start()
            self.addCleanup(guard.stop)

    def write(self):
        self.path.write_text(json.dumps(self.config), encoding="utf-8")

    def cli(self, *arguments):
        output, errors = io.StringIO(), io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = osc.main(list(arguments))
        return code, output.getvalue(), errors.getvalue()

    def make_plan(self, value=3, reset=0, parameter="FaceMode", avatar=AVATAR):
        return osc.plan(self.path, avatar, parameter, value, reset)

    def test_inspect_separates_config_inputs_outputs_and_custom_routes(self):
        self.config["parameters"] += [
            {"name": "VelocityZ", "output": {"address": "/avatar/parameters/VelocityZ", "type": "Float"}},
            {"name": "OutOnly", "output": {"address": "/other/application", "type": "bool"}},
            entry("Custom", input_address="/input/Jump"),
        ]
        self.write()
        result = osc.inspect_config(self.path)
        self.assertEqual([item["name"] for item in result["writable_inputs"]], ["FaceMode"])
        self.assertEqual({item["name"]: item["reason"] for item in result["blocked_inputs"]},
                         {"VelocityZ": "builtin_read_only", "OutOnly": "no_input", "Custom": "nonstandard_input_requires_review"})
        self.assertEqual(result["outputs"][2]["address"], "/other/application")
        self.assertFalse(result["sent"])
        self.assertFalse(result["runtime_verified"])

    def test_plan_binds_exact_config_bytes_and_has_explicit_set_and_reset(self):
        before = self.path.read_bytes()
        result = self.make_plan()
        self.assertEqual(result["config"]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(result["config"]["avatar_id"], AVATAR)
        self.assertEqual(result["config"]["filename_avatar_id"], AVATAR)
        self.assertTrue(result["avatar_id_matches_config"])
        self.assertFalse(result["active_client_avatar_verified"])
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["sent"])
        self.assertEqual([(step["action"], step["value"]) for step in result["steps"]], [("set", 3), ("reset", 0)])
        self.assertEqual(result["mode"], "plan_only")
        self.assertEqual(result["port_defaults"], {"vrchat_receives": 9000, "vrchat_sends": 9001,
                                                   "configurable": True, "observed": False})
        self.assertEqual(self.path.read_bytes(), before)

    def test_int_packet_uses_null_padding_and_big_endian_signed_int32(self):
        result = self.make_plan(3, -2147483648)
        self.assertEqual(bytes.fromhex(result["steps"][0]["osc"]["packet_hex"]),
                         b"/avatar/parameters/FaceMode\0,i\0\0\x00\x00\x00\x03")
        reset = bytes.fromhex(result["steps"][1]["osc"]["packet_hex"])
        self.assertEqual(reset[-4:], b"\x80\x00\x00\x00")
        self.assertEqual(result["steps"][0]["osc"]["type_tag"], ",i")
        self.assertEqual(len(reset) % 4, 0)

    def test_bool_packets_use_T_F_tags_without_argument_bytes(self):
        self.config["parameters"] = [entry("Flag", "Bool")]
        self.write()
        result = self.make_plan(True, False, "Flag")
        self.assertEqual(bytes.fromhex(result["steps"][0]["osc"]["packet_hex"]), b"/avatar/parameters/Flag\0,T\0\0")
        self.assertEqual(bytes.fromhex(result["steps"][1]["osc"]["packet_hex"]), b"/avatar/parameters/Flag\0,F\0\0")
        self.assertEqual(result["steps"][0]["osc"]["byte_length"], 28)

    def test_float_packet_uses_float32_and_reports_wire_rounding(self):
        self.config["parameters"] = [entry("Blend", "Float")]
        self.write()
        result = self.make_plan(0.5, -1, "Blend")
        self.assertEqual(bytes.fromhex(result["steps"][0]["osc"]["packet_hex"]),
                         b"/avatar/parameters/Blend\0\0\0\0,f\0\0\x3f\x00\x00\x00")
        self.assertEqual(bytes.fromhex(result["steps"][1]["osc"]["packet_hex"])[-4:], b"\xbf\x80\x00\x00")
        result = self.make_plan(0.1, 0, "Blend")
        self.assertEqual(result["steps"][0]["osc"]["encoded_value"], struct.unpack(">f", b"\x3d\xcc\xcc\xcd")[0])
        self.assertNotEqual(result["steps"][0]["osc"]["encoded_value"], result["steps"][0]["value"])

    def test_wrong_json_scalar_types_are_rejected_without_coercion(self):
        invalid = {"Bool": [0, 1, "true", None, [], {}],
                   "Int": [True, False, 1.0, "3", None, []],
                   "Float": [True, False, "0.5", None, [], {}]}
        for kind, values in invalid.items():
            self.config["parameters"] = [entry("FaceMode", kind)]
            self.write()
            reset = False if kind == "Bool" else 0
            for value in values:
                with self.subTest(kind=kind, value=value), self.assertRaises(osc.OSCPlanError):
                    self.make_plan(value, reset)

    def test_int32_boundaries_and_reset_type_are_enforced(self):
        for value in (-2147483648, 2147483647):
            self.assertEqual(self.make_plan(value)["steps"][0]["value"], value)
        for value in (-2147483649, 2147483648):
            with self.subTest(value=value), self.assertRaises(osc.OSCPlanError):
                self.make_plan(value)
        with self.assertRaises(osc.OSCPlanError):
            self.make_plan(3, False)

    def test_float_rejects_nonfinite_and_overflow_in_both_steps(self):
        self.config["parameters"] = [entry("Blend", "Float")]
        self.write()
        for value in (math.nan, math.inf, -math.inf, 1e40, 10 ** 400):
            with self.subTest(value=str(value)[:10]), self.assertRaises(osc.OSCPlanError):
                self.make_plan(value, 0, "Blend")
            with self.assertRaises(osc.OSCPlanError):
                self.make_plan(0, value, "Blend")

    def test_avatar_and_canonical_filename_must_match_config(self):
        with self.assertRaises(osc.OSCPlanError):
            self.make_plan(avatar=OTHER)
        self.config["id"] = OTHER
        self.write()
        with self.assertRaisesRegex(osc.OSCPlanError, "filename"):
            osc.inspect_config(self.path)

    def test_exported_filename_does_not_claim_client_filename_verification(self):
        exported = self.root / "copied-config.json"
        exported.write_bytes(self.path.read_bytes())
        result = osc.plan(exported, AVATAR, "FaceMode", 1, 0)
        self.assertIsNone(result["config"]["filename_avatar_id"])
        self.assertFalse(result["active_client_avatar_verified"])

    def test_all_official_read_only_parameters_stay_blocked_even_with_spoofed_input(self):
        self.config["parameters"] = [entry(name) for name in sorted(osc.READ_ONLY)]
        self.write()
        self.assertEqual(osc.inspect_config(self.path)["writable_inputs"], [])
        for name in osc.READ_ONLY:
            with self.subTest(name=name), self.assertRaisesRegex(osc.OSCPlanError, "builtin_read_only"):
                self.make_plan(parameter=name)

    def test_output_only_and_unavailable_parameters_cannot_be_planned(self):
        for value in ({"name": "Only", "output": {"address": "/avatar/parameters/Only", "type": "Int"}},
                      {"name": "Only", "input": None, "output": None}):
            self.config["parameters"] = [value]
            self.write()
            with self.assertRaisesRegex(osc.OSCPlanError, "no_input"):
                self.make_plan(parameter="Only")

    def test_movement_chatbox_avatar_change_and_parameter_redirects_cannot_be_planned(self):
        for address in ("/input/Jump", "/chatbox/input", "/avatar/change", "/avatar/parameters/Other"):
            self.config["parameters"] = [entry("FaceMode", input_address=address)]
            self.write()
            self.assertEqual(osc.inspect_config(self.path)["blocked_inputs"][0]["input"]["address"], address)
            with self.subTest(address=address), self.assertRaisesRegex(osc.OSCPlanError, "requires_review"):
                self.make_plan()

    def test_names_are_not_trimmed_slugged_casefolded_or_pattern_expanded(self):
        for name in ("Face Mode", " FaceMode", "Face*", "Face?", "Face[1]", "Face{A,B}", "Faccè"):
            self.config["parameters"] = [entry(name)]
            self.write()
            self.assertEqual(osc.inspect_config(self.path)["blocked_inputs"][0]["name"], name)
            with self.subTest(name=name), self.assertRaisesRegex(osc.OSCPlanError, "requires_review"):
                self.make_plan(parameter=name)
        self.config["parameters"] = [entry("FaceMode")]
        self.write()
        with self.assertRaises(osc.OSCPlanError):
            self.make_plan(parameter="facemode")

    def test_duplicate_json_keys_at_any_level_and_duplicate_parameter_names_fail(self):
        for content in ('{"id":"x","id":"y"}',
                        json.dumps(self.config).replace('"type": "Int"', '"type":"Int","type":"Float"', 1)):
            self.path.write_text(content)
            with self.assertRaisesRegex(osc.OSCPlanError, "Duplicate JSON key"):
                osc.load_config(self.path)
        self.config["parameters"].append(copy.deepcopy(self.config["parameters"][0]))
        self.write()
        with self.assertRaisesRegex(osc.OSCPlanError, "Duplicate parameter"):
            osc.load_config(self.path)

    def test_one_input_route_cannot_silently_control_multiple_parameters(self):
        self.config["parameters"].append(entry("Other", input_address="/avatar/parameters/FaceMode"))
        self.write()
        with self.assertRaisesRegex(osc.OSCPlanError, "Duplicate OSC input address"):
            self.make_plan()

    def test_malformed_config_schema_types_lengths_and_nonfinite_json_fail(self):
        valid = copy.deepcopy(self.config)
        for change in ({"id": "avtr_invalid"}, {"name": ""}, {"parameters": {}},
                       {"parameters": [entry("x" * (osc.MAX_NAME_BYTES + 1))]},
                       {"parameters": [{"name": "FaceMode", "input": {"address": "/x", "type": "bool"}}]},
                       {"parameters": [{"name": "FaceMode", "input": {"address": "/x", "type": []}}]},
                       {"parameters": [entry("FaceMode", input_address="/x" + "a" * osc.MAX_ADDRESS_BYTES)]}):
            self.config = {**valid, **change}
            self.write()
            with self.subTest(change=list(change)), self.assertRaises(osc.OSCPlanError):
                osc.load_config(self.path)
        self.path.write_text('{"id":NaN}')
        with self.assertRaises(osc.OSCPlanError):
            osc.load_config(self.path)

    def test_config_size_count_path_and_symlink_are_bounded(self):
        with patch.object(osc, "MAX_CONFIG_BYTES", 10), self.assertRaises(osc.OSCPlanError):
            osc.load_config(self.path)
        with patch.object(osc, "MAX_PARAMETERS", 0), self.assertRaises(osc.OSCPlanError):
            osc.load_config(self.path)
        with patch.object(osc, "MAX_PATH_BYTES", 10), self.assertRaises(osc.OSCPlanError):
            osc.load_config(self.path)
        link = self.root / "link.json"
        try:
            link.symlink_to(self.path)
        except OSError:
            return
        with self.assertRaises(osc.OSCPlanError):
            osc.load_config(link)

    def test_cli_requires_reset_and_has_no_send_option(self):
        base = ["plan", str(self.path), "--avatar", AVATAR, "--parameter", "FaceMode", "--value", "3"]
        for arguments in (base, [*base, "--reset", "0", "--send"]):
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as raised:
                osc.main(arguments)
            self.assertEqual(raised.exception.code, 2)

    def test_cli_inspect_and_plan_are_offline_and_optional_output_is_new_only(self):
        code, output, errors = self.cli("inspect", str(self.path))
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(len(json.loads(output)["writable_inputs"]), 1)
        destination = self.root / "plan.json"
        args = ("plan", str(self.path), "--avatar", AVATAR, "--parameter", "FaceMode", "--value", "3", "--reset", "0", "--out", str(destination))
        code, output, errors = self.cli(*args)
        self.assertEqual((code, errors), (0, ""))
        self.assertEqual(json.loads(destination.read_text()), json.loads(output))
        before = destination.read_bytes()
        code, output, _ = self.cli(*args)
        self.assertEqual((code, output), (2, ""))
        self.assertEqual(destination.read_bytes(), before)
        original = self.path.read_bytes()
        code, output, _ = self.cli(*args[:-1], str(self.path))
        self.assertEqual((code, output), (2, ""))
        self.assertEqual(self.path.read_bytes(), original)

    def test_invalid_value_or_reset_does_not_create_output(self):
        destination = self.root / "invalid-plan.json"
        for value, reset in (("true", "0"), ("3", "false"), ("NaN", "0"), ("3", "Infinity"), ("[1]", "0")):
            code, output, _ = self.cli("plan", str(self.path), "--avatar", AVATAR, "--parameter", "FaceMode",
                                       "--value", value, "--reset", reset, "--out", str(destination))
            self.assertEqual((code, output), (2, ""))
            self.assertFalse(destination.exists())

    def test_missing_config_is_an_error_not_runtime_evidence(self):
        code, output, _ = self.cli("inspect", str(self.root / "not-generated-by-build-and-test.json"))
        self.assertEqual((code, output), (2, ""))

    def test_helper_has_no_transport_imports(self):
        imports = set()
        for node in ast.walk(ast.parse(SCRIPT.read_text())):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module.split(".")[0])
        self.assertTrue(imports.isdisjoint({"socket", "urllib", "http", "requests", "subprocess", "asyncio"}))


if __name__ == "__main__":
    unittest.main()
