"""Offline transport tests. No key, paid submission or real network required."""

import hashlib
from http.client import IncompleteRead
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import ssl
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request


SCRIPT = Path(__file__).resolve().parents[1] / "skills" / "funavatar" / "scripts" / "tripo_api.py"
SPEC = importlib.util.spec_from_file_location("funavatar_tripo_transport_test", SCRIPT)
api = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = api
SPEC.loader.exec_module(api)


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None):
        super().__init__(data)
        self.status = status
        self.code = status
        self.msg = "response"
        self.headers = headers or {}

    def info(self):
        return self.headers


def envelope(data):
    return Response(json.dumps({"code": 0, "data": data}).encode())


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.client = api.TripoClient(api_key="secret-unit-test-key")
        self.client._opener = Mock()

    def test_submit_unwraps_fixed_endpoint_once(self):
        self.client._opener.open.return_value = envelope({"task_id": "task_abc"})
        self.assertEqual(self.client.submit("text_to_model", {"prompt": "avatar"}),
                         {"task_id": "task_abc"})
        self.client._opener.open.assert_called_once()
        request = self.client._opener.open.call_args.args[0]
        self.assertEqual(request.full_url,
                         "https://openapi.tripo3d.ai/v3/generation/text-to-model")
        self.assertEqual(request.get_header("Authorization"), "Bearer secret-unit-test-key")
        self.assertEqual(request.method, "POST")

    def test_no_automatic_retry_on_uncertain_post(self):
        for error in (TimeoutError("secret-unit-test-key"),
                      URLError("https://signed.invalid/?token=private"),
                      HTTPError("https://signed.invalid/?secret=x", 503,
                                "private", {}, None)):
            with self.subTest(error=type(error).__name__):
                self.client._opener.open.reset_mock()
                self.client._opener.open.side_effect = error
                with self.assertRaises(api.SubmissionUncertain) as caught:
                    self.client.submit("rig", {"input": "task_abc"})
                self.client._opener.open.assert_called_once()
                self.assertNotIn("secret-unit-test-key", str(caught.exception))
                self.assertNotIn("https://", str(caught.exception))

    def test_invalid_submit_responses_are_uncertain(self):
        for data in (b"<html>secret</html>", b'{"code":0,"data":{}}',
                     b'{"code":true,"data":{}}', b'{"code":0,"data":{"cost":NaN}}',
                     b"x" * (api.MAX_JSON_BYTES + 1)):
            with self.subTest(length=len(data)):
                self.client._opener.open.return_value = Response(data)
                with self.assertRaises(api.SubmissionUncertain):
                    self.client.submit("image_to_model", {"input": "file_abc"})

    def test_provider_error_does_not_echo_raw_body(self):
        self.client._opener.open.return_value = Response(
            b'{"code":2010,"message":"secret-unit-test-key https://private/?token=x"}')
        with self.assertRaises(api.APIError) as caught:
            self.client.submit("rig", {"input": "task_abc"})
        self.assertNotIsInstance(caught.exception, api.SubmissionUncertain)
        self.assertEqual(caught.exception.code, 2010)
        self.assertNotIn("secret-unit", str(caught.exception))
        self.assertNotIn("https://", str(caught.exception))

    def test_authenticated_redirect_is_never_followed(self):
        handler = api._NoRedirect()
        self.assertIsNone(handler.redirect_request(None, None, 307, "redirect", {},
                                                  "https://untrusted.invalid"))
        self.client._opener.open.side_effect = HTTPError(
            "https://openapi.tripo3d.ai/v3/animations/rig", 307, "redirect",
            {"Location": "https://untrusted.invalid"}, None)
        with self.assertRaises(api.SubmissionUncertain):
            self.client.submit("rig", {"input": "task_abc"})
        self.client._opener.open.assert_called_once()

    def test_invalid_operation_payload_and_id_do_not_connect(self):
        for operation, payload in (("smart_uv", {}), ("text_to_model", []),
                                   ("text_to_model", {"prompt": float("nan")})):
            with self.assertRaises(api.APIError):
                self.client.submit(operation, payload)
        with self.assertRaises(api.APIError):
            self.client.get_task("task_abc/../../account")
        self.client._opener.open.assert_not_called()

    def test_task_query_and_balance_get(self):
        self.client._opener.open.side_effect = [
            envelope({"task_id": "task_abc", "status": "running", "progress": 30}),
            envelope({"balance": 100.0, "frozen": 15.0})]
        self.assertEqual(self.client.get_task("task_abc")["progress"], 30)
        self.assertEqual(self.client.get_balance()["frozen"], 15.0)
        for call in self.client._opener.open.call_args_list:
            self.assertEqual(call.args[0].method, "GET")

    def test_get_incomplete_response_is_safe_api_error(self):
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.status = 200
        response.read.side_effect = IncompleteRead(b"private")
        self.client._opener.open.return_value = response
        with self.assertRaises(api.APIError) as caught:
            self.client.get_task("task_abc")
        self.assertNotIsInstance(caught.exception, api.SubmissionUncertain)
        self.assertNotIn("private", str(caught.exception))

    def test_env_and_region_are_constrained(self):
        with patch.dict(os.environ, {"TRIPO_API_KEY": "env-test-key"}):
            self.assertEqual(api.TripoClient()._api_key, "env-test-key")
        with self.assertRaises(api.APIError):
            api.TripoClient(api_key="line\r\ninjection")
        with self.assertRaises(api.APIError):
            api.TripoClient(api_key="test", region="https://evil.invalid")

    def test_upload_streams_bounded_multipart_and_hides_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'private-name".png'
            path.write_bytes(b"example-image")
            captured = {}

            def open_upload(request, **kwargs):
                captured["request"] = request
                captured["body"] = b"".join(request.data)
                return envelope({"file_token": "file_abc"})

            self.client._opener.open.side_effect = open_upload
            self.assertEqual(self.client.upload_file(path), {"file_token": "file_abc"})
            body = captured["body"]
            self.assertIn(b'filename="asset.png"', body)
            self.assertIn(b"example-image", body)
            self.assertNotIn(b"private-name", body)
            self.assertEqual(int(captured["request"].get_header("Content-length")), len(body))

    def test_upload_rejects_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "source.png"
            source.write_bytes(b"image")
            alias = Path(tmp) / "alias.png"
            alias.symlink_to(source)
            with self.assertRaises(api.APIError):
                self.client.upload_file(alias)
            self.client._opener.open.assert_not_called()


class AssetTests(unittest.TestCase):
    def setUp(self):
        self.client = api.TripoClient(api_key="secret-unit-test-key")

    def test_https_public_only(self):
        for url in ("http://example.com/asset", "https://user:pass@example.com/asset",
                    "https://localhost/asset", "https://example.com:8443/asset",
                    "file:///tmp/file", "https://example.com/asset#fragment"):
            with self.subTest(url=url), self.assertRaises(api.APIError):
                api._public_addresses(url)
        for address in ("127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254",
                        "::1", "fc00::1", "::ffff:127.0.0.1", "2002:c0a8:1::1"):
            answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))]
            with self.subTest(address=address), patch.object(api.socket, "getaddrinfo",
                                                           return_value=answers):
                with self.assertRaises(api.APIError):
                    api._public_addresses("https://example.com/asset")

    def test_mixed_public_private_dns_is_rejected(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))
                   for address in ("8.8.8.8", "127.0.0.1")]
        with patch.object(api.socket, "getaddrinfo", return_value=answers):
            with self.assertRaises(api.APIError):
                api._public_addresses("https://example.com/asset")

    def test_asset_connection_pins_validated_ip_and_uses_original_tls_hostname(self):
        raw = Mock()
        captured = {}

        def open_connection(handler, connection_class, request, **kwargs):
            connection = connection_class(request.host, context=kwargs["context"], timeout=5)
            connection.connect()
            captured["connection"] = connection
            return Response(b"asset")

        with patch.object(api.HTTPSHandler, "do_open", autospec=True,
                          side_effect=open_connection):
            with patch.object(api.socket, "create_connection", return_value=raw) as connect:
                with patch.object(ssl.SSLContext, "wrap_socket", return_value=Mock()) as wrap:
                    opener = api._download_opener("asset.example", ["8.8.8.8"])
                    opener.open(Request("https://asset.example/model"), timeout=5).close()
        self.assertEqual(connect.call_args.args[0], ("8.8.8.8", 443))
        self.assertEqual(wrap.call_args.kwargs["server_hostname"], "asset.example")

    def test_redirects_are_validated_and_never_authenticated(self):
        opener = Mock()
        opener.open.side_effect = [
            HTTPError("https://example.com/model?token=hidden", 302, "redirect",
                      {"Location": "https://other.example/asset?token=hidden"}, None),
            Response(b"model")]
        with patch.object(api, "_public_addresses", return_value=("example.com", 443,
                                                                  ["8.8.8.8"])) as validate:
            with patch.object(api, "_download_opener", return_value=opener):
                self.client._open_asset("https://example.com/model?token=hidden").close()
        self.assertEqual(validate.call_count, 2)
        self.assertEqual(validate.call_args.args[0], "https://other.example/asset?token=hidden")
        for call in opener.open.call_args_list:
            self.assertIsNone(call.args[0].get_header("Authorization"))

    def test_redirect_to_private_host_is_blocked(self):
        opener = Mock()
        opener.open.side_effect = HTTPError("https://example.com/asset", 302, "redirect",
                                           {"Location": "https://127.0.0.1/private"}, None)
        with patch.object(api, "_public_addresses", side_effect=[
            ("example.com", 443, ["8.8.8.8"]), api.APIError("Public HTTPS required.")]):
            with patch.object(api, "_download_opener", return_value=opener):
                with self.assertRaises(api.APIError):
                    self.client._open_asset("https://example.com/asset")
        opener.open.assert_called_once()

    def test_download_is_atomic_hashed_and_no_clobber(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "model.glb"
            content = b"a model" * 10000
            with patch.object(self.client, "_open_asset", return_value=Response(
                    content, headers={"Content-Length": str(len(content))})):
                result = self.client.download("https://example.com/model?secret=x", target)
            self.assertEqual(target.read_bytes(), content)
            self.assertEqual(result["sha256"], hashlib.sha256(content).hexdigest())
            self.assertEqual(result["bytes"], len(content))
            self.assertEqual(set(result), {"path", "sha256", "bytes"})
            self.assertEqual(list(Path(tmp).resolve().iterdir()), [target])
            with patch.object(self.client, "_open_asset") as open_asset:
                with self.assertRaises(api.APIError):
                    self.client.download("https://example.com/model", target)
                open_asset.assert_not_called()
            self.assertEqual(target.read_bytes(), content)

    def test_incomplete_download_removes_temp_and_leaves_no_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "model.glb"
            with patch.object(self.client, "_open_asset", return_value=Response(
                    b"short", headers={"Content-Length": "100"})):
                with self.assertRaises(api.APIError):
                    self.client.download("https://example.com/model?secret=x", target)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_oversized_download_is_rejected_before_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(self.client, "_open_asset", return_value=Response(
                    b"", headers={"Content-Length": str(api.MAX_DOWNLOAD_BYTES + 1)})):
                with self.assertRaises(api.APIError):
                    self.client.download("https://example.com/model", Path(tmp).resolve() / "model.glb")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_stream_limit_is_enforced_without_content_length(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(api, "MAX_DOWNLOAD_BYTES", 4):
                with patch.object(self.client, "_open_asset", return_value=Response(b"12345")):
                    with self.assertRaises(api.APIError):
                        self.client.download("https://example.com/model",
                                             Path(tmp).resolve() / "model.glb")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_symlink_destination_and_parent_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp).resolve()
            original = base / "original.glb"
            original.write_bytes(b"original")
            alias = base / "model.glb"
            alias.symlink_to(original)
            with self.assertRaises(api.APIError):
                self.client.download("https://example.com/model", alias)
            folder = base / "real"
            folder.mkdir()
            linked_folder = base / "linked"
            linked_folder.symlink_to(folder, target_is_directory=True)
            with self.assertRaises(api.APIError):
                self.client.download("https://example.com/model", linked_folder / "model.glb")
            self.assertEqual(original.read_bytes(), b"original")


if __name__ == "__main__":
    unittest.main()
