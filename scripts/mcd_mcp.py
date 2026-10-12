#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""麦当劳中国 MCP 客户端（Streamable HTTP + JSON-RPC 2.0）。

零第三方依赖，只用 Python 标准库。

鉴权
----
Token 从环境变量 ``MCD_MCP_TOKEN`` 读取（在 https://open.mcd.cn/mcp 激活获取）。
Token 等同你的麦当劳会员身份，**不要写进代码、不要提交到仓库**。

用法
----
    python mcd_mcp.py list                          # 列出服务端暴露的全部工具
    python mcd_mcp.py call query-meals '{"storeCode":"S001"}'
    python mcd_mcp.py ask query-meals storeCode=S001
    python mcd_mcp.py ping                          # 连通性 + 耗时
    python mcd_mcp.py list --mock                    # 无 Token 时用内置假数据跑通
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from mcd_schema import build_items, normalize_stores, order_params  # noqa: E402

DEFAULT_URL = "https://mcp.mcd.cn"
PROTOCOL_VERSION = "2025-06-18"
DEFAULT_TIMEOUT = 30
CLIENT_INFO = {"name": "mcd-nailong-skill", "version": "1.0.0"}
STORE_CACHE_FILE = Path(__file__).resolve().parent / ".mcd_stores.json"


class McdMcpError(RuntimeError):
    """MCP 调用失败。"""


# --------------------------------------------------------------------------- #
# 响应解包
# --------------------------------------------------------------------------- #
def extract_result(result: Any) -> Any:
    """把 MCP tools/call 返回的 content 结构摊平成 Python 对象。

    优先取 ``structuredContent``；否则拼接 text 片段并尝试 JSON 解析。
    """
    if not isinstance(result, dict):
        return result
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    parts: list[str] = []
    for item in result.get("content") or []:
        if isinstance(item, dict) and item.get("type") == "text":
            parts.append(str(item.get("text", "")))
    text = "\n".join(parts).strip()
    if not text:
        return result
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


# --------------------------------------------------------------------------- #
# 客户端
# --------------------------------------------------------------------------- #
class McdMcpClient:
    """极简 MCP Streamable HTTP 客户端。"""

    def __init__(
        self,
        token: str | None = None,
        url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        mock: bool = False,
    ) -> None:
        self.url = (url or os.environ.get("MCD_MCP_URL") or DEFAULT_URL).rstrip("/")
        self.token = (token if token is not None else os.environ.get("MCD_MCP_TOKEN", "")).strip()
        self.timeout = timeout
        self.mock = mock
        self._session_id: str | None = None
        self._rpc_id = 0
        self._initialized = False
        self._calls = 0
        self._store_cache: dict[str, dict] = {}
        self._store_cache_loaded = False

        if mock:
            import mock_data  # 同目录，延迟导入

            self._mock = mock_data
            return
        if not self.token:
            raise McdMcpError(
                "缺少 MCP Token。请先在 https://open.mcd.cn/mcp 激活并复制 Token，\n"
                "然后设置环境变量 MCD_MCP_TOKEN（Windows: setx MCD_MCP_TOKEN \"你的Token\"）。"
            )

    # ----------------------------- 传输层 ----------------------------- #
    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Authorization": f"Bearer {self.token}",
            "MCP-Protocol-Version": PROTOCOL_VERSION,
        }
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        return headers

    def _post(self, payload: dict, notify: bool = False) -> dict | None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers=self._headers(), method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                session = resp.headers.get("Mcp-Session-Id") or resp.headers.get("mcp-session-id")
                if session:
                    self._session_id = session
                raw = resp.read().decode("utf-8", "replace")
                ctype = (resp.headers.get("Content-Type") or "").lower()
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:400]
            raise McdMcpError(f"HTTP {exc.code} - {detail}") from exc
        except urllib.error.URLError as exc:
            raise McdMcpError(f"网络不可达：{exc.reason}") from exc

        if notify or not raw.strip():
            return None
        return _parse_payload(raw, ctype)

    def _rpc(self, method: str, params: dict | None = None, notify: bool = False) -> Any:
        self._rpc_id += 1
        payload: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            payload["params"] = params
        if not notify:
            payload["id"] = self._rpc_id

        message = self._post(payload, notify=notify)
        if notify or message is None:
            return None
        error = message.get("error")
        if error:
            raise McdMcpError(f"{error.get('code')} {error.get('message')}")
        return message.get("result")

    # ----------------------------- 协议层 ----------------------------- #
    def initialize(self) -> None:
        if self._initialized or self.mock:
            self._initialized = True
            return
        self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": CLIENT_INFO,
            },
        )
        try:
            self._rpc("notifications/initialized", {}, notify=True)
        except McdMcpError:
            pass
        self._initialized = True

    def list_tools(self) -> list[dict]:
        if self.mock:
            return self._mock.MOCK_TOOLS
        self.initialize()
        result = self._rpc("tools/list", {}) or {}
        return result.get("tools", [])

    def call_tool(self, name: str, arguments: dict | None = None, retries: int = 2) -> Any:
        """调用一个 MCP 工具，自动重试限流错误。"""
        if self.mock:
            self._calls += 1
            return self._mock.mock_call(name, arguments or {})

        self.initialize()
        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                self._calls += 1
                result = self._rpc("tools/call", {"name": name, "arguments": arguments or {}})
                if isinstance(result, dict) and result.get("isError"):
                    raise McdMcpError(f"工具 {name} 返回错误：{extract_result(result)}")
                return extract_result(result)
            except McdMcpError as exc:
                last_error = exc
                text = str(exc).lower()
                if "429" in text or "rate" in text or "too many" in text:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise
        raise last_error  # type: ignore[misc]

    # --------------------------- 门店上下文 --------------------------- #
    def store_context(self, store_code: str, refresh: bool = False) -> dict:
        """解析 storeCode -> 完整门店信息。

        下单类接口需要 ``beCode``，而它**只能从门店接口拿到**（不能凭空生成）。
        这里做一层缓存：先查内存、再查 ``.mcd_stores.json``，最后才请求 query-nearby-stores。
        """
        if not refresh and store_code in self._store_cache:
            return dict(self._store_cache[store_code])

        if not self._store_cache_loaded:
            self._load_store_cache()
        if not refresh and store_code in self._store_cache:
            return dict(self._store_cache[store_code])

        try:
            for store in normalize_stores(self.nearby_stores()):
                self._store_cache[store["code"]] = store
            self._save_store_cache()
        except McdMcpError:
            pass

        return dict(self._store_cache.get(store_code, {"code": store_code, "beCode": ""}))

    def _load_store_cache(self) -> None:
        self._store_cache_loaded = True
        if self.mock:
            return
        try:
            if STORE_CACHE_FILE.exists():
                data = json.loads(STORE_CACHE_FILE.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    self._store_cache.update(data)
        except (json.JSONDecodeError, OSError):
            pass

    def _save_store_cache(self) -> None:
        if self.mock:
            return
        try:
            STORE_CACHE_FILE.write_text(
                json.dumps(self._store_cache, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    # --------------------------- 业务便捷方法 --------------------------- #
    def now(self) -> dict:
        return _as_dict(self.call_tool("now-time-info"))

    def nearby_stores(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("query-nearby-stores", kwargs))

    def delivery_addresses(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("delivery-query-addresses", kwargs))

    def meals(self, store_code: str, **kwargs) -> dict:
        """拉菜单。带上 beCode 更稳（并非所有门店接口都要求，缺省时不阻塞）。"""
        ctx = self.store_context(store_code)
        args: dict[str, Any] = {"storeCode": store_code}
        if ctx.get("beCode"):
            args["beCode"] = ctx["beCode"]
        args.update(kwargs)
        return _as_dict(self.call_tool("query-meals", args))

    def meal_detail(self, meal_code: str, store_code: str | None = None) -> dict:
        args: dict[str, Any] = {"mealCode": meal_code}
        if store_code:
            args["storeCode"] = store_code
        return _as_dict(self.call_tool("query-meal-detail", args))

    def _order_payload(self, store_code: str, items: Any, dining_mode: str) -> dict:
        """按官方契约组装 calculate-price / create-order 的公共入参。"""
        ctx = self.store_context(store_code)
        payload: dict[str, Any] = {
            "storeCode": store_code,
            "items": build_items(items),
            **order_params(dining_mode),
        }
        if ctx.get("beCode"):
            payload["beCode"] = ctx["beCode"]
        return payload

    def calculate_price(self, store_code: str, items: Any, dining_mode: str = "dine_in", **kwargs) -> dict:
        """算价。入参字段按官方契约（orderType / beType / beCode / items[productCode,quantity]）。"""
        payload = self._order_payload(store_code, items, dining_mode)
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return _as_dict(self.call_tool("calculate-price", payload))

    def create_order(
        self,
        store_code: str,
        items: Any,
        dining_mode: str = "dine_in",
        take_way_code: str | None = None,
        address_id: str | None = None,
        remark: str | None = None,
        **kwargs,
    ) -> dict:
        """创建订单。

        ⚠️ **本调用不扣款**：它只生成一笔「待支付」订单并返回 ``payH5Url``（扫码支付页）。
        真实扣款发生在用户自己打开该链接完成支付时；超时未支付订单会被自动取消。
        """
        payload = self._order_payload(store_code, items, dining_mode)
        if take_way_code:
            payload["takeWayCode"] = take_way_code
        if address_id:
            payload["addressId"] = address_id
        if remark:
            payload["remark"] = str(remark)[:50]
        payload.update({k: v for k, v in kwargs.items() if v is not None})
        return _as_dict(self.call_tool("create-order", payload))

    def store_coupons(self, store_code: str) -> dict:
        return _as_dict(self.call_tool("query-store-coupons", {"storeCode": store_code}))

    def available_coupons(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("available-coupons", kwargs))

    def auto_bind_coupons(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("auto-bind-coupons", kwargs))

    def my_coupons(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("my-coupons", kwargs))

    def campaign_calendar(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("campaign-calendar", kwargs))

    def nutrition(self, **kwargs) -> dict:
        return _as_dict(self.call_tool("list-nutrition-foods", kwargs))

    def query_order(self, order_id: str) -> dict:
        return _as_dict(self.call_tool("query-order", {"orderId": order_id}))

    @property
    def call_count(self) -> int:
        return self._calls


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #
def _parse_payload(raw: str, content_type: str) -> dict:
    """兼容 application/json 与 text/event-stream 两种响应体。"""
    stripped = raw.lstrip()
    looks_like_sse = "text/event-stream" in content_type or stripped.startswith("event:") or stripped.startswith("data:")
    if not looks_like_sse:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise McdMcpError(f"响应不是合法 JSON：{raw[:300]}") from exc

    last: dict | None = None
    for line in raw.splitlines():
        line = line.strip()
        if not line.startswith("data:"):
            continue
        chunk = line[5:].strip()
        if not chunk or chunk == "[DONE]":
            continue
        try:
            message = json.loads(chunk)
        except json.JSONDecodeError:
            continue
        if "result" in message or "error" in message:
            last = message
    if last is None:
        raise McdMcpError(f"无法解析 SSE 响应：{raw[:300]}")
    return last


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {"items": value}
    if value is None:
        return {}
    return {"value": value}


def parse_kv(pairs: list[str]) -> dict:
    """把 ["a=1", "b=2"] 解析成 {"a": "1", "b": "2"}，自动做 JSON 类型转换。"""
    out: dict[str, Any] = {}
    for pair in pairs:
        if "=" not in pair:
            raise McdMcpError(f"参数格式应为 key=value，收到：{pair}")
        key, _, raw = pair.partition("=")
        try:
            out[key] = json.loads(raw)
        except json.JSONDecodeError:
            out[key] = raw
    return out


def pprint(value: Any) -> None:
    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=False, indent=2)
        if len(text) > 6000:
            text = text[:6000] + "\n... (已截断)"
        print(text)
    else:
        print(value)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main(argv: list[str]) -> int:
    if not argv or argv[0] in {"-h", "--help"}:
        print(__doc__)
        return 0

    mock = "--mock" in argv
    argv = [a for a in argv if a != "--mock"]
    command = argv[0]

    try:
        client = McdMcpClient(mock=mock)
    except McdMcpError as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        return 2

    if command == "list":
        tools = client.list_tools()
        print(f"共 {len(tools)} 个工具" + ("（内置假数据）" if mock else ""))
        for tool in tools:
            print(f"- {tool.get('name')}: {(tool.get('description') or '').splitlines()[0][:90]}")
        return 0

    if command == "ping":
        started = time.time()
        now = client.now()
        print(f"连通正常，耗时 {time.time() - started:.2f}s")
        pprint(now)
        return 0

    if command == "call":
        if len(argv) < 2:
            print("用法：python mcd_mcp.py call <tool> ['{json}']", file=sys.stderr)
            return 2
        args = json.loads(argv[2]) if len(argv) > 2 else {}
        pprint(client.call_tool(argv[1], args))
        return 0

    if command == "ask":
        if len(argv) < 2:
            print("用法：python mcd_mcp.py ask <tool> key=value ...", file=sys.stderr)
            return 2
        pprint(client.call_tool(argv[1], parse_kv(argv[2:])))
        return 0

    print(f"未知命令：{command}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
