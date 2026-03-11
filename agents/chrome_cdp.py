#!/usr/bin/env python3
"""Shared Chrome CDP helpers for browser-backed CLI tools."""

import asyncio
import json
import random
import urllib.request

import websockets


def fetch_cdp_targets(base_url):
    """Fetch current CDP targets from a Chrome instance."""
    with urllib.request.urlopen(f"{base_url}/json/list") as resp:
        return json.loads(resp.read())


def find_target_ws_url(base_url, predicate):
    """Find a page target websocket URL matching predicate(page)."""
    for page in fetch_cdp_targets(base_url):
        if page.get("type") != "page":
            continue
        if predicate(page):
            return page["webSocketDebuggerUrl"]
    return None


class ChromeCDP:
    """Minimal async CDP client for a single page target."""

    def __init__(self, base_url, target_predicate):
        self.base_url = base_url
        self.target_predicate = target_predicate
        self.ws = None
        self.pending = {}
        self.reader_task = None

    async def connect(self):
        ws_url = find_target_ws_url(self.base_url, self.target_predicate)
        if not ws_url:
            raise RuntimeError(f"Target page not found in Chrome at {self.base_url}")
        self.ws = await websockets.connect(ws_url, max_size=50 * 1024 * 1024)
        self.reader_task = asyncio.create_task(self._reader())

    async def _reader(self):
        try:
            async for raw in self.ws:
                msg = json.loads(raw)
                mid = msg.get("id")
                if mid and mid in self.pending and not self.pending[mid].done():
                    self.pending[mid].set_result(msg)
        except Exception:
            pass

    async def cdp_call(self, method, params=None, timeout=20):
        mid = random.randint(10000, 99999)
        req = {"id": mid, "method": method, "params": params or {}}
        loop = asyncio.get_event_loop()
        fut = loop.create_future()
        self.pending[mid] = fut
        await self.ws.send(json.dumps(req))
        resp = await asyncio.wait_for(fut, timeout=timeout)
        self.pending.pop(mid, None)
        if "error" in resp:
            raise RuntimeError(json.dumps(resp["error"], ensure_ascii=False))
        return resp

    async def evaluate(self, expression, timeout=20):
        resp = await self.cdp_call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "awaitPromise": True,
                "returnByValue": True,
            },
            timeout=timeout,
        )
        result = resp.get("result", {})
        if "exceptionDetails" in result:
            raise RuntimeError(
                json.dumps(result["exceptionDetails"], ensure_ascii=False)
            )
        return result.get("result", {}).get("value")

    async def insert_text(self, text):
        await self.cdp_call("Input.insertText", {"text": text})

    async def click_at(self, x, y):
        for event_type in ("mouseMoved", "mousePressed", "mouseReleased"):
            params = {"type": event_type, "x": x, "y": y, "button": "left"}
            if event_type in ("mousePressed", "mouseReleased"):
                params["clickCount"] = 1
            await self.cdp_call("Input.dispatchMouseEvent", params)

    async def close(self):
        if self.reader_task:
            self.reader_task.cancel()
        if self.ws:
            await self.ws.close()
