#!/usr/bin/env python3
"""
URL/HTML screenshot service — renders web content via headless Chromium.

Each WebSocket connection represents one persistent browser page. Client
sends JSON commands:
  {"cmd":"open","url":"https://..."}  or  {"cmd":"open","html":"<!doctype..."}
  {"cmd":"shot","w":800,"h":600}      -> server returns binary JPEG
  {"cmd":"click","x":100,"y":50}
  {"cmd":"scroll","dy":100}
  {"cmd":"key","key":"Enter"}
  {"cmd":"goto","url":"..."}

Server replies:
  - Binary JPEG for shot commands
  - {"ok":true} or {"err":"..."} for control commands (JSON text)
"""
import asyncio
import json
import logging
import os
import sys

import websockets
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("snap_server")

HOST = os.environ.get("SNAP_HOST", "0.0.0.0")
PORT = int(os.environ.get("SNAP_PORT", "8084"))


async def handle_client(ws, browser):
    peer = ws.remote_address
    log.info("Snap client connected: %s", peer)
    ctx = await browser.new_context(viewport={"width": 1280, "height": 720})
    page = await ctx.new_page()
    try:
        async for msg in ws:
            if not isinstance(msg, str):
                continue
            try:
                cmd = json.loads(msg)
            except Exception:
                continue
            op = cmd.get("cmd")
            try:
                if op == "open" or op == "goto":
                    url = cmd.get("url")
                    if url:
                        await page.goto(url, timeout=20000, wait_until="domcontentloaded")
                        await ws.send(json.dumps({"ok": True, "cmd": op}))
                    elif cmd.get("html"):
                        await page.set_content(cmd["html"], wait_until="domcontentloaded")
                        await ws.send(json.dumps({"ok": True, "cmd": op}))
                elif op == "shot":
                    w = int(cmd.get("w", 1280))
                    h = int(cmd.get("h", 720))
                    if w != ctx._options.get("viewport", {}).get("width", 0) or h != ctx._options.get("viewport", {}).get("height", 0):
                        await page.set_viewport_size({"width": w, "height": h})
                    img = await page.screenshot(type="jpeg", quality=70, full_page=False, timeout=5000)
                    await ws.send(img)
                elif op == "click":
                    x = int(cmd.get("x", 0))
                    y = int(cmd.get("y", 0))
                    await page.mouse.click(x, y)
                    await ws.send(json.dumps({"ok": True, "cmd": "click"}))
                elif op == "scroll":
                    dy = int(cmd.get("dy", 100))
                    await page.evaluate(f"window.scrollBy(0, {dy})")
                    await ws.send(json.dumps({"ok": True, "cmd": "scroll"}))
                elif op == "key":
                    k = cmd.get("key", "")
                    await page.keyboard.press(k)
                    await ws.send(json.dumps({"ok": True, "cmd": "key"}))
                else:
                    await ws.send(json.dumps({"err": f"unknown cmd: {op}"}))
            except Exception as e:
                log.warning("Command error (%s): %s", op, e)
                try:
                    await ws.send(json.dumps({"err": str(e)}))
                except Exception:
                    break
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        log.error("Client handler error: %s", e)
    finally:
        try:
            await ctx.close()
        except Exception:
            pass
        log.info("Snap client disconnected: %s", peer)


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        log.info("Chromium launched")

        async def handler(ws):
            await handle_client(ws, browser)

        log.info("Listening on ws://%s:%d", HOST, PORT)
        async with websockets.serve(handler, HOST, PORT, max_size=16 * 1024 * 1024,
                                     ping_interval=20, ping_timeout=60):
            await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
