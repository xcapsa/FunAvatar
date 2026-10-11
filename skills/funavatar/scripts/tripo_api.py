#!/usr/bin/env python3
"""Small, non-retrying Tripo v3 transport. Python 3.10+, standard library only.

Budget reservations and resumable task state belong to the caller. This module
never replays POST requests, never logs provider bodies or signed output URLs,
and never forwards the API key to downloaded assets. Endpoints were checked
against https://developers.tripo3d.ai/en/docs/introduction on 2026-10-11.
"""

from __future__ import annotations

import hashlib
import http.client
import ipaddress
import json
import math
import os
from pathlib import Path
import re
import secrets
import socket
import ssl
import stat
from typing import Iterator
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import (HTTPSHandler, HTTPRedirectHandler, ProxyHandler,
                            Request, build_opener)


API_ORIGINS = {
    "global": "https://openapi.tripo3d.ai/v3",
    "china": "https://openapi.tripo3d.com/v3",
}
# No guessed endpoint for Studio-only features (including Smart UV/import).
OPERATIONS = {
    "text_to_model": "/generation/text-to-model",
    "image_to_model": "/generation/image-to-model",
    "multiview_to_model": "/generation/multiview-to-model",
    "texture": "/models/texture",
    "retopology": "/mesh/decimate",
    "segment": "/mesh/segment",
    "complete": "/mesh/complete",
    "rig_check": "/animations/rig-check",
    "rig": "/animations/rig",
    "retarget": "/animations/retarget",
    "convert": "/models/convert",
}
MAX_JSON_BYTES = 2 * 1024 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MAX_DOWNLOAD_BYTES = 1024 * 1024 * 1024
CHUNK_BYTES = 64 * 1024
TASK_ID = re.compile(r"task_[A-Za-z0-9_-]{1,200}\Z")
FILE_TOKEN = re.compile(r"file_[A-Za-z0-9_-]{1,200}\Z")
UPLOAD_TYPES = {
    ".jpg": ("image/jpeg", 20 * 1024 * 1024),
    ".jpeg": ("image/jpeg", 20 * 1024 * 1024),
    ".png": ("image/png", 20 * 1024 * 1024),
    ".glb": ("model/gltf-binary", 150 * 1024 * 1024),
    ".gltf": ("model/gltf+json", 150 * 1024 * 1024),
    ".fbx": ("application/octet-stream", 150 * 1024 * 1024),
    ".obj": ("application/octet-stream", 150 * 1024 * 1024),
    ".stl": ("application/octet-stream", 150 * 1024 * 1024),
}


class APIError(RuntimeError):
    """Safe transport error; response bodies and URLs are deliberately omitted."""

    def __init__(self, message: str, *, status: int | None = None,
                 code: int | None = None):
        super().__init__(message)
        self.status = status
        self.code = code


class SubmissionUncertain(APIError):
    """The provider may have received the POST. Do not resubmit automatically."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _public_addresses(url: str) -> tuple[str, int, list[str]]:
    """Validate every DNS answer and return pinned public addresses.

    Resolving once and connecting to those addresses prevents a second DNS
    answer from turning an accepted hostname into a private-network request.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port or 443
        if (parts.scheme != "https" or not host or parts.username is not None
                or parts.password is not None or port != 443 or parts.fragment
                or len(url) > 16384 or any(ord(c) < 33 for c in url)
                or "%" in host or "\\" in host):
            raise ValueError
        if (host.lower() == "localhost" or host.lower().endswith(".localhost")
                or host.lower().endswith(".local")):
            raise ValueError
        answers = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = []
        for answer in answers:
            address = answer[4][0]
            parsed = ipaddress.ip_address(address)
            # Explicitly disallow IPv4-mapped IPv6 even if a runtime classifies
            # the wrapping address as public.
            if (not parsed.is_global or getattr(parsed, "ipv4_mapped", None)
                    or getattr(parsed, "sixtofour", None) is not None
                    or getattr(parsed, "teredo", None) is not None):
                raise ValueError
            if address not in addresses:
                addresses.append(address)
        if not addresses:
            raise ValueError
        return host, port, addresses
    except (ValueError, OSError):
        raise APIError("Asset URL must resolve only to public HTTPS addresses.") from None


def _download_opener(hostname: str, addresses: list[str]):
    class PinnedHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            last_error = None
            for address in addresses:
                raw = None
                try:
                    raw = socket.create_connection((address, self.port), self.timeout,
                                                   self.source_address)
                    self.sock = self._context.wrap_socket(raw, server_hostname=hostname)
                    return
                except OSError as error:
                    last_error = error
                    if raw is not None:
                        raw.close()
            raise OSError("Could not connect to the validated asset host.") from last_error

    class PinnedHTTPSHandler(HTTPSHandler):
        def https_open(self, req):
            return self.do_open(PinnedHTTPSConnection, req,
                                context=ssl.create_default_context())

    return build_opener(ProxyHandler({}), _NoRedirect(), PinnedHTTPSHandler())


def _invalid_constant(value):
    raise ValueError("Non-finite JSON constant")


def _open_directory_without_symlinks(path: Path) -> int:
    """Walk with directory FDs so ancestor symlink swaps cannot redirect writes."""
    flags = os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path.anchor, flags)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = next_fd
        return fd
    except BaseException:
        os.close(fd)
        raise


def _read_json(response, *, uncertain: bool) -> dict:
    error_class = SubmissionUncertain if uncertain else APIError
    raw = response.read(MAX_JSON_BYTES + 1)
    if len(raw) > MAX_JSON_BYTES:
        raise error_class("Tripo response exceeded the JSON size limit.")
    try:
        result = json.loads(raw, parse_constant=_invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise error_class("Tripo returned an invalid JSON response.") from None
    if not isinstance(result, dict) or type(result.get("code")) is not int:
        raise error_class("Tripo returned an invalid response envelope.")
    if result["code"] != 0:
        # Error text may repeat prompts, tokens or URLs. Only the numeric code
        # is safe and needed by the registry.
        raise APIError("Tripo rejected the request (provider code %s)." % result["code"],
                       code=result["code"])
    if not isinstance(result.get("data"), dict):
        raise error_class("Tripo returned invalid task data.")
    return result["data"]


class TripoClient:
    def __init__(self, api_key: str | None = None, region: str = "global",
                 timeout: float = 30):
        if region not in API_ORIGINS:
            raise APIError("Unsupported Tripo region; use global or china.")
        key = os.environ.get("TRIPO_API_KEY") if api_key is None else api_key
        if (not isinstance(key, str) or not key or len(key) > 4096
                or any(ord(c) < 33 or ord(c) > 126 for c in key)):
            raise APIError("Set a valid TRIPO_API_KEY environment variable.")
        if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
                or not math.isfinite(timeout) or timeout <= 0 or timeout > 300):
            raise APIError("Timeout must be between zero and 300 seconds.")
        self._api_key = key
        self.region = region
        self.timeout = timeout
        self._base_url = API_ORIGINS[region]
        # Never use ambient proxies or forward Authorization through a redirect.
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _request(self, path: str, *, body=None, content_type: str | None = None,
                 content_length: int | None = None) -> dict:
        post = body is not None
        headers = {"Authorization": "Bearer " + self._api_key,
                   "Accept": "application/json", "User-Agent": "FunAvatar-Tripo/1"}
        if content_type:
            headers["Content-Type"] = content_type
        if content_length is not None:
            headers["Content-Length"] = str(content_length)
        req = Request(self._base_url + path, data=body, headers=headers,
                      method="POST" if post else "GET")
        try:
            with self._opener.open(req, timeout=self.timeout) as response:
                status = response.status
                if status != 200:
                    cls = SubmissionUncertain if post else APIError
                    raise cls("Tripo returned an unexpected HTTP status.", status=status)
                return _read_json(response, uncertain=post)
        except HTTPError as error:
            status = error.code
            error.close()
            cls = (SubmissionUncertain if post and
                   (status >= 500 or status == 408 or 300 <= status < 400) else APIError)
            raise cls("Tripo request failed (HTTP %s)." % status, status=status) from None
        except APIError:
            raise
        except (OSError, URLError, http.client.HTTPException):
            cls = SubmissionUncertain if post else APIError
            raise cls("Tripo request did not return a complete response.") from None

    def submit(self, operation: str, payload: dict) -> dict:
        if operation not in OPERATIONS:
            raise APIError("Unsupported or unverified Tripo operation.")
        if not isinstance(payload, dict):
            raise APIError("Tripo payload must be a JSON object.")
        try:
            body = json.dumps(payload, ensure_ascii=False, allow_nan=False,
                              separators=(",", ":")).encode("utf-8")
        except (ValueError, TypeError, UnicodeError, RecursionError):
            raise APIError("Tripo payload is not valid JSON.") from None
        if len(body) > MAX_REQUEST_BYTES:
            raise APIError("Tripo payload exceeded the request size limit.")
        data = self._request(OPERATIONS[operation], body=body,
                             content_type="application/json")
        if not isinstance(data.get("task_id"), str) or not TASK_ID.fullmatch(data["task_id"]):
            raise SubmissionUncertain("Tripo accepted a request without a valid task identifier.")
        return data

    def get_task(self, task_id: str) -> dict:
        if not isinstance(task_id, str) or not TASK_ID.fullmatch(task_id):
            raise APIError("Invalid Tripo task identifier.")
        data = self._request("/tasks/" + task_id)
        if data.get("task_id") != task_id:
            raise APIError("Tripo returned a different task identifier.")
        return data

    def get_balance(self) -> dict:
        """Read provider credits; this is separate from the local budget cap."""
        return self._request("/account/balance")

    def upload_file(self, path: str | os.PathLike) -> dict:
        path = Path(path)
        file_type = UPLOAD_TYPES.get(path.suffix.lower())
        if file_type is None:
            raise APIError("Unsupported Tripo upload file type.")
        mime, limit = file_type
        fd = None
        try:
            fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or not 0 < info.st_size <= limit:
                raise APIError("Upload must be a regular file within the provider size limit.")
            boundary = "FunAvatar" + secrets.token_hex(16)
            # Use a neutral filename so quotes, paths and private names never
            # become multipart headers sent to the provider.
            prefix = ("--%s\r\nContent-Disposition: form-data; name=\"file\"; "
                      "filename=\"asset%s\"\r\nContent-Type: %s\r\n\r\n" %
                      (boundary, path.suffix.lower(), mime)).encode("ascii")
            suffix = ("\r\n--%s--\r\n" % boundary).encode("ascii")

            def chunks() -> Iterator[bytes]:
                yield prefix
                remaining = info.st_size
                while remaining:
                    chunk = os.read(fd, min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise OSError("Upload file changed while reading.")
                    remaining -= len(chunk)
                    yield chunk
                if os.read(fd, 1):
                    raise OSError("Upload file changed while reading.")
                yield suffix

            data = self._request("/files", body=chunks(),
                                 content_type="multipart/form-data; boundary=" + boundary,
                                 content_length=len(prefix) + info.st_size + len(suffix))
            if (not isinstance(data.get("file_token"), str)
                    or not FILE_TOKEN.fullmatch(data["file_token"])):
                raise SubmissionUncertain("Tripo upload returned no valid file token.")
            return data
        except APIError:
            raise
        except OSError:
            raise APIError("Upload file could not be opened safely.") from None
        finally:
            if fd is not None:
                os.close(fd)

    def download(self, url: str, destination: str | os.PathLike) -> dict:
        """Stream a public HTTPS asset to a new file, atomically, without auth."""
        if not isinstance(url, str):
            raise APIError("Asset URL must be a string.")
        destination = Path(os.path.abspath(destination))
        if destination.name in {"", ".", ".."}:
            raise APIError("Invalid asset destination.")
        # Reject symlink components; hold an opened parent directory throughout
        # the write/commit so a concurrent rename cannot redirect the output.
        try:
            parent_fd = _open_directory_without_symlinks(destination.parent)
        except APIError:
            raise
        except OSError:
            raise APIError("Asset destination directory could not be opened safely.") from None
        temporary = ".funavatar-download-" + secrets.token_hex(16)
        temp_exists = False
        try:
            try:
                os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise APIError("Asset destination already exists; overwrite is forbidden.")
            response = self._open_asset(url)
            with response:
                header_size = response.headers.get("Content-Length")
                if header_size is not None:
                    try:
                        expected = int(header_size)
                    except ValueError:
                        raise APIError("Asset response has an invalid size header.") from None
                    if expected < 0 or expected > MAX_DOWNLOAD_BYTES:
                        raise APIError("Asset exceeds the download size limit.")
                else:
                    expected = None
                fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=parent_fd)
                temp_exists = True
                digest = hashlib.sha256()
                total = 0
                with os.fdopen(fd, "wb") as stream:
                    while True:
                        chunk = response.read(CHUNK_BYTES)
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise APIError("Asset exceeds the download size limit.")
                        stream.write(chunk)
                        digest.update(chunk)
                    if total == 0 or (expected is not None and total != expected):
                        raise APIError("Asset download was empty or incomplete.")
                    stream.flush()
                    os.fsync(stream.fileno())
            # link() is an atomic no-clobber commit, unlike replace()/rename().
            os.link(temporary, destination.name, src_dir_fd=parent_fd,
                    dst_dir_fd=parent_fd, follow_symlinks=False)
            os.unlink(temporary, dir_fd=parent_fd)
            temp_exists = False
            os.fsync(parent_fd)
            return {"path": str(destination), "sha256": digest.hexdigest(), "bytes": total}
        except APIError:
            raise
        except (OSError, URLError, http.client.HTTPException):
            raise APIError("Asset download or safe file commit failed.") from None
        finally:
            if temp_exists:
                try:
                    os.unlink(temporary, dir_fd=parent_fd)
                except OSError:
                    pass
            os.close(parent_fd)

    def _open_asset(self, url: str):
        for _ in range(6):
            host, _, addresses = _public_addresses(url)
            opener = _download_opener(host, addresses)
            request = Request(url, headers={"User-Agent": "FunAvatar-Tripo/1"}, method="GET")
            try:
                response = opener.open(request, timeout=self.timeout)
                if response.status != 200:
                    response.close()
                    raise APIError("Asset server returned an unexpected HTTP status.")
                return response
            except HTTPError as error:
                status = error.code
                location = error.headers.get("Location")
                error.close()
                if status in {301, 302, 303, 307, 308} and location:
                    url = urljoin(url, location)
                    continue
                raise APIError("Asset request failed (HTTP %s)." % status, status=status) from None
            except APIError:
                raise
            except (OSError, URLError, http.client.HTTPException):
                raise APIError("Asset request did not return a complete response.") from None
        raise APIError("Asset request exceeded the redirect limit.")
