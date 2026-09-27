"""
Collector cho BSC qua BSCTrace (MegaNode/NodeReal) — thay thế BscScan API đã
deprecated (2025-12), dùng khi Etherscan free-tier không hỗ trợ BSC.

Khác EtherscanClient (REST module=action): BSCTrace dùng JSON-RPC 2.0, một
method duy nhất `nr_getAssetTransfers` gộp cả external/internal/20(=ERC-20)/
721/1155/state/deposit/withdraw transfer (tương đương txlist+tokentx+
txlistinternal của Etherscan). Giá trị category CHÍNH XÁC (xác nhận qua lỗi
API thật 2026-08-13, không phải suy đoán từ tài liệu): {external, internal,
20, 721, 1155, state, deposit, withdraw} — LƯU Ý "20" không phải "erc20".

Field mapping (value đã là số thập phân human-readable, blockNum hex string,
metadata.blockTimestamp ISO8601) — xem `smoke_test()` để tự xác nhận trước
khi tin tưởng dữ liệu hàng loạt.

API key đọc từ biến môi trường BSCTRACE_API_KEY (hoặc MEGANODE_API_KEY),
KHÔNG hardcode.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_DIR = REPO_ROOT / "data" / "raw"
BASE_URL_TEMPLATE = "https://bsc-mainnet.nodereal.io/v1/{api_key}"

# Nạp .env ở gốc repo (nếu có) vào os.environ, giống src/collect/etherscan_client.py
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)

DEFAULT_CATEGORIES = ["external", "internal", "20"]  # bỏ 721/1155/state/deposit/withdraw - ngoài scope CAGI-ED (chỉ token fungible); giá trị "20" (không phải "erc20") xác nhận qua lỗi API thật 2026-08-13


class BscTraceAPIError(RuntimeError):
    """Lỗi trả về từ BSCTrace JSON-RPC (field "error" trong response)."""


class BscTraceClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        max_retries: int = 5,
        backoff_base_sec: float = 1.0,
        timeout_sec: float = 20.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else (
            os.environ.get("BSCTRACE_API_KEY") or os.environ.get("MEGANODE_API_KEY")
        )
        if not self.api_key:
            raise ValueError(
                "Thiếu BSCTRACE_API_KEY (hoặc MEGANODE_API_KEY). Đăng ký free tại "
                "nodereal.io/meganode, lấy API key cho BNB Chain, đặt vào .env — "
                "không hardcode key trong code."
            )
        self.cache_dir = Path(cache_dir)
        self.max_retries = max_retries
        self.backoff_base_sec = backoff_base_sec
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()
        self.base_url = BASE_URL_TEMPLATE.format(api_key=self.api_key)

    # ------------------------------------------------------------------
    # Core JSON-RPC + cache + retry
    # ------------------------------------------------------------------
    def _cache_path(self, address: str, incident_id: str, page_idx: int) -> Path:
        # Cache SCOPED theo incident_id (bug #6, xem annotation_guide.md mục
        # 15) — cùng lý do với EtherscanClient._cache_path (src/collect/
        # etherscan_client.py): tránh 2 incident dùng chung 1 địa chỉ hạ
        # tầng phổ biến ghi đè cache của nhau khi cửa sổ khác nhau.
        d = self.cache_dir / "bsc" / address.lower() / incident_id
        d.mkdir(parents=True, exist_ok=True)
        return d / f"assettransfers_w{page_idx}.json"

    def _write_cache(self, path: Path, payload: Dict[str, Any], raw_text: str) -> None:
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        record = {
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "response": payload,
        }
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def _rpc_call(self, method: str, params: List[Any], cache_path: Optional[Path] = None) -> Dict[str, Any]:
        body = {"jsonrpc": "2.0", "method": method, "params": params, "id": 1}

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.post(self.base_url, json=body, timeout=self.timeout_sec)
            except requests.exceptions.Timeout as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue
            except requests.exceptions.RequestException as exc:
                last_exc = exc
                self._sleep_backoff(attempt)
                continue

            if resp.status_code == 429:
                self._sleep_backoff(attempt)
                continue

            resp.raise_for_status()
            payload = resp.json()

            error = payload.get("error")
            if error is not None:
                message = str(error.get("message", "")).lower()
                if "rate limit" in message or "too many" in message:
                    self._sleep_backoff(attempt)
                    continue
                raise BscTraceAPIError(f"BSCTrace JSON-RPC lỗi: {error}")

            if cache_path is not None:
                self._write_cache(cache_path, payload, resp.text)
            return payload

        raise BscTraceAPIError(
            f"Hết số lần retry ({self.max_retries}) khi gọi BSCTrace API. Lỗi cuối: {last_exc}"
        )

    def _sleep_backoff(self, attempt: int) -> None:
        time.sleep(self.backoff_base_sec * (2 ** attempt))

    # ------------------------------------------------------------------
    # Public fetch function
    # ------------------------------------------------------------------
    def fetch_asset_transfers(
        self,
        address: str,
        incident_id: str,
        categories: Optional[List[str]] = None,
        page_size: int = 100,
        max_pages: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Gọi nr_getAssetTransfers, tự phân trang qua `pageKey` tới khi hết
        (field phân trang THẬT xác nhận qua response thật 2026-08-13 — không
        phải "pageToken"/"nextPageToken" như tài liệu công khai gợi ý).

        `from_block`/`to_block` (int, không phải hex): tham số KHÔNG có
        trong tài liệu công khai của BSCTrace nhưng ĐÃ XÁC NHẬN hoạt động
        thật qua request thật ngày 2026-08-13 (server lọc đúng theo block
        range yêu cầu). Nếu None, KHÔNG gửi tham số này (server trả theo
        thứ tự mặc định — có thể không phủ đúng khung thời gian mong muốn,
        bug thật gặp phải khi mining hard-negative cho BSC Token Hub: cache
        mặc định chỉ phủ block 1-1,021,501, bỏ sót hoàn toàn khung
        ~21.7M-21.9M cần thiết).
        """
        categories = categories or DEFAULT_CATEGORIES
        # Xoá SẠCH file cache outbound cũ (w0..w999) của (address, incident_id)
        # trước khi fetch lại — cùng lý do với EtherscanClient (xem comment
        # trong src/collect/etherscan_client.py._fetch_all_pages): tránh để
        # lại trang cache THỪA từ 1 lần gọi TRƯỚC (của CHÍNH incident_id này)
        # có window rộng hơn/nhiều trang hơn lần này, đảm bảo chỉ có ĐÚNG 1
        # thế hệ cache. KHÔNG đụng cache của incident_id khác (bug #6).
        stale_dir = self.cache_dir / "bsc" / address.lower() / incident_id
        if stale_dir.exists():
            for idx in range(max_pages):
                stale_file = self._cache_path(address, incident_id, idx)
                if stale_file.exists():
                    stale_file.unlink()

        all_rows: List[Dict[str, Any]] = []
        page_key = ""
        for page_idx in range(max_pages):
            params = {
                "fromAddress": address,
                "category": categories,
                "withMetadata": True,
                "excludeZeroValue": False,
                "pageSize": page_size,
                "pageKey": page_key,
            }
            if from_block is not None:
                params["fromBlock"] = hex(from_block)
            if to_block is not None:
                params["toBlock"] = hex(to_block)
            cache_path = self._cache_path(address, incident_id, page_idx)
            payload = self._rpc_call("nr_getAssetTransfers", [params], cache_path=cache_path)
            result = payload.get("result") or {}
            transfers = result.get("transfers", [])
            all_rows.extend(transfers)

            page_key = result.get("pageKey") or ""
            if not page_key or not transfers:
                break
        return all_rows

    def fetch_asset_transfers_bidirectional(
        self,
        address: str,
        incident_id: str,
        categories: Optional[List[str]] = None,
        page_size: int = 100,
        from_block: Optional[int] = None,
        to_block: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """fromAddress + toAddress riêng biệt (API có 2 tham số khác nhau,
        không giống Etherscan trả cả 2 chiều trong 1 lần gọi theo `address`).
        """
        categories = categories or DEFAULT_CATEGORIES
        out_rows = self.fetch_asset_transfers(
            address, incident_id, categories=categories, page_size=page_size, from_block=from_block, to_block=to_block
        )

        # Xoá sạch cache inbound cũ (namespace w1000+) của (address, incident_id) — cùng lý do outbound ở trên.
        stale_dir = self.cache_dir / "bsc" / address.lower() / incident_id
        if stale_dir.exists():
            for idx in range(100):
                stale_file = self._cache_path(address, incident_id, idx + 1000)
                if stale_file.exists():
                    stale_file.unlink()

        in_rows: List[Dict[str, Any]] = []
        page_key = ""
        for page_idx in range(100):
            params = {
                "toAddress": address,
                "category": categories,
                "withMetadata": True,
                "excludeZeroValue": False,
                "pageSize": page_size,
                "pageKey": page_key,
            }
            if from_block is not None:
                params["fromBlock"] = hex(from_block)
            if to_block is not None:
                params["toBlock"] = hex(to_block)
            cache_path = self._cache_path(address, incident_id, page_idx + 1000)  # tách namespace khỏi outbound
            payload = self._rpc_call("nr_getAssetTransfers", [params], cache_path=cache_path)
            result = payload.get("result") or {}
            transfers = result.get("transfers", [])
            in_rows.extend(transfers)
            page_key = result.get("pageKey") or ""
            if not page_key or not transfers:
                break

        # dedup theo (hash, category, logIndex) — logIndex là field thật,
        # duy nhất trong phạm vi 1 tx_hash+category, tránh đếm trùng khi
        # transfer xuất hiện ở cả 2 lần gọi (from==to, hoặc lệch trang).
        seen = set()
        merged = []
        for row in out_rows + in_rows:
            key = (row.get("hash"), row.get("category"), row.get("logIndex"))
            if key not in seen:
                seen.add(key)
                merged.append(row)
        return merged


def smoke_test(address: str = "0xd01ae1a708614948b2b5e0b7ab5be6afa01325c7") -> None:  # pragma: no cover
    """Gọi thử 1 lần với key thật để XÁC NHẬN schema response trước khi tin
    tưởng dữ liệu hàng loạt (field mapping trong module này dựa theo tài
    liệu công khai, chưa test với key thật khi viết code).

    Chạy: python -c "from src.collect.bsctrace_client import smoke_test; smoke_test()"
    """
    client = BscTraceClient()
    rows = client.fetch_asset_transfers(address, incident_id="smoke_test", page_size=5)
    print(f"Nhận {len(rows)} transfer(s). In 1 record đầu để kiểm tra field:")
    if rows:
        print(json.dumps(rows[0], indent=2))
    else:
        print("(Không có transfer nào — kiểm tra lại address/category)")
