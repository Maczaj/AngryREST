#!/usr/bin/env python3
"""Minimal test server for verifying AngryREST body types.

Run:  python test_server.py
Endpoints (all POST):
  http://localhost:8765/json
  http://localhost:8765/form
  http://localhost:8765/multipart
  (any other path works too)
"""
from __future__ import annotations

import cgi
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        content_length = int(self.headers.get("Content-Length", 0) or 0)

        print(f"\n{'='*60}")
        print(f"POST {self.path}")
        print("Headers:")
        for name, value in self.headers.items():
            print(f"  {name}: {value}")

        if "application/json" in content_type:
            raw = self.rfile.read(content_length)
            try:
                data = json.loads(raw)
                print("JSON body:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
            except json.JSONDecodeError as exc:
                print(f"Invalid JSON ({exc}): {raw.decode(errors='replace')}")

        elif "application/x-www-form-urlencoded" in content_type:
            raw = self.rfile.read(content_length)
            from urllib.parse import parse_qs
            fields = parse_qs(raw.decode(errors="replace"))
            print("Form fields:")
            for k, vs in fields.items():
                print(f"  {k!r} = {vs!r}")

        elif "multipart/form-data" in content_type:
            environ = {
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": content_type,
                "CONTENT_LENGTH": str(content_length),
            }
            storage = cgi.FieldStorage(
                fp=self.rfile,
                headers=self.headers,
                environ=environ,
            )
            print("Multipart fields:")
            for key in storage.keys():
                item = storage[key]
                if isinstance(item, list):
                    items = item
                else:
                    items = [item]
                for field in items:
                    if field.filename:
                        data = field.file.read()
                        print(
                            f"  [file]  field={key!r}  filename={field.filename!r}"
                            f"  mime={field.type!r}  size={len(data):,} bytes"
                        )
                        preview = data[:80]
                        try:
                            print(f"          preview: {preview.decode()!r}")
                        except UnicodeDecodeError:
                            print(f"          preview (hex): {preview.hex()}")
                    else:
                        print(f"  [text]  field={key!r}  value={field.value!r}")

        else:
            raw = self.rfile.read(content_length)
            print(f"Raw body ({len(raw)} bytes): {raw[:200]!r}")

        self._respond({"status": "ok", "path": self.path})

    def do_GET(self) -> None:
        print(f"\n{'='*60}")
        print(f"GET {self.path}")
        print("Headers:")
        for name, value in self.headers.items():
            print(f"  {name}: {value}")
        self._respond({"status": "ok", "path": self.path})

    def _respond(self, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args: object) -> None:
        pass  # suppress default access log; we print our own above


if __name__ == "__main__":
    host, port = "localhost", 8765
    server = HTTPServer((host, port), _Handler)
    print(f"Test server listening on http://{host}:{port}")
    print("Send POST requests from AngryREST to any path — body will be printed here.")
    print("Ctrl-C to stop.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
