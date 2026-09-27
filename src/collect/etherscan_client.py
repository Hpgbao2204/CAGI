"""
Collector cho Etherscan-family API (Etherscan/BscScan/Arbiscan hợp nhất qua
API V2: api.etherscan.io/v2/api?chainid=...). Xem configs/data.yaml ->
explorer_api.

- Cache mọi response thô vào data/raw/{chain}/{address}/ dạng JSON, kèm
  checksum (sha256) + timestamp request.
- Retry với exponential backoff khi gặp rate limit (429/mã lỗi rate limit
  của Etherscan) hoặc timeout.
- API key đọc từ biến môi trường ETHERSCAN_API_KEY, KHÔNG hardcode. Nếu có
  file .env ở gốc repo (không commit — xem .gitignore), key được tự động
  nạp vào os.environ qua python-dotenv trước khi đọc.
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

# Nạp .env ở gốc repo (nếu có) vào os.environ. override=False: biến môi
# trường đã đặt sẵn trong shell (vd export/setx) luôn được ưu tiên hơn .env.
load_dotenv(dotenv_path=REPO_ROOT / ".env", override=False)
API_BASE_URL = "https://api.etherscan.io/v2/api"

# chain_id theo API V2 hợp nhất (vd https://docs.etherscan.io/v2-migration)
CHAIN_IDS = {
    "eth": 1,
    "bsc": 56,
    "arbitrum": 42161,
}

# Các mã lỗi/thông điệp Etherscan-family trả về khi bị rate limit, cần retry.
RATE_LIMIT_MARKERS = (
    "max rate limit reached",
    "max calls per sec",
)


class EtherscanAPIError(RuntimeError):
    """Lỗi trả về từ Etherscan API (status != '1' và không phải rate limit)."""


class EtherscanClient:
    def __init__(
        self,
        api_key: Optional[str] = None,
        cache_dir: Path = DEFAULT_CACHE_DIR,
        max_retries: int = 5,
        backoff_base_sec: float = 1.0,
        timeout_sec: float = 15.0,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get("ETHERSCAN_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Thiếu ETHERSCAN_API_KEY. Đặt biến môi trường ETHERSCAN_API_KEY trước khi "
                "dùng EtherscanClient (không hardcode key trong code)."
            )
        self.cache_dir = Path(cache_dir)
        self.max_retries = max_retries
        self.backoff_base_sec = backoff_base_sec
        self.timeout_sec = timeout_sec
        self.session = session or requests.Session()

    # ------------------------------------------------------------------
    # Core HTTP + cache + retry
    # ------------------------------------------------------------------
    def _cache_path(self, chain: str, address: str, incident_id: str, action: str, start_block: int) -> Path:
        # Cache SCOPED theo incident_id (bug #6, xem annotation_guide.md mục
        # 15) — trước đây cache chỉ theo (chain, address), nên khi 2 incident
        # khác nhau cùng chạm 1 địa chỉ hạ tầng phổ biến (không phải leak
        # thật, xem dataset_card.md mục Exclusions) với cửa sổ block khác
        # nhau, ai fetch SAU ghi đè cache của người TRƯỚC một cách âm thầm —
        # phát hiện thật ở qbridge_qubit_2022 ↔ paraluni_2022 (địa chỉ
        # 0xdd90e5e8...). Nested thêm 1 tầng thư mục incident_id đảm bảo 2
        # incident không bao giờ đụng file của nhau, bất kể thứ tự fetch.
        d = self.cache_dir / chain / address.lower() / incident_id
        d.mkdir(parents=True, exist_ok=True)
        return d / f"{action}_from_{start_block}.json"

    def _write_cache(self, path: Path, payload: Dict[str, Any], raw_text: str) -> None:
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        record = {
            "requested_at_utc": datetime.now(timezone.utc).isoformat(),
            "checksum_sha256": checksum,
            "response": payload,
        }
        path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    def _get(self, chain: str, params: Dict[str, Any], cache_path: Optional[Path] = None) -> Dict[str, Any]:
        if chain not in CHAIN_IDS:
            raise ValueError(f"Chain '{chain}' không nằm trong CHAIN_IDS đã cấu hình: {list(CHAIN_IDS)}")

        query = dict(params)
        query["chainid"] = CHAIN_IDS[chain]
        query["apikey"] = self.api_key

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(API_BASE_URL, params=query, timeout=self.timeout_sec)
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

            # Etherscan có thể trả text rate-limit ở "message" HOẶC "result"
            # (vd {"status":"0","message":"NOTOK","result":"Max calls per sec
            # rate limit reached (3/sec)"}) — phải kiểm tra cả hai field.
            message_text = f"{payload.get('message', '')} {payload.get('result', '')}".lower()
            if payload.get("status") == "0" and any(marker in message_text for marker in RATE_LIMIT_MARKERS):
                self._sleep_backoff(attempt)
                continue

            if cache_path is not None:
                self._write_cache(cache_path, payload, resp.text)
            return payload

        raise EtherscanAPIError(
            f"Hết số lần retry ({self.max_retries}) khi gọi Etherscan API. Lỗi cuối: {last_exc}"
        )

    def _sleep_backoff(self, attempt: int) -> None:
        time.sleep(self.backoff_base_sec * (2 ** attempt))

    # ------------------------------------------------------------------
    # Public fetch functions
    #
    # Etherscan-family API giới hạn tối đa 10.000 record/call (page*offset
    # <= 10000). Với địa chỉ hoạt động mạnh (vd contract vừa bị hack), số
    # lượng tx có thể vượt xa mốc đó trong 1 block range cố định -> phải
    # phân trang: fetch offset=page_size, nếu trả về đủ page_size record thì
    # đẩy startblock lên block cuối cùng đã nhận (sort=asc) và lặp lại,
    # dedup theo (hash, logIndex nếu có) để không đếm trùng tx nằm ở biên
    # giữa 2 lần gọi.
    # ------------------------------------------------------------------
    def fetch_normal_txs(
        self, chain: str, address: str, incident_id: str, start_block: int = 0, end_block: int = 99_999_999
    ) -> List[Dict[str, Any]]:
        """Etherscan module=account&action=txlist (có phân trang)."""
        return self._fetch_all_pages(
            chain, address, incident_id, action="txlist", start_block=start_block, end_block=end_block,
            dedup_key=lambda row: (row.get("hash"),),
        )

    def fetch_erc20_transfers(
        self, chain: str, address: str, incident_id: str, start_block: int = 0, end_block: int = 99_999_999
    ) -> List[Dict[str, Any]]:
        """Etherscan module=account&action=tokentx (có phân trang)."""
        return self._fetch_all_pages(
            chain, address, incident_id, action="tokentx", start_block=start_block, end_block=end_block,
            dedup_key=lambda row: (row.get("hash"), row.get("logIndex")),
        )

    def fetch_internal_txs(
        self, chain: str, address: str, incident_id: str, start_block: int = 0, end_block: int = 99_999_999
    ) -> List[Dict[str, Any]]:
        """Etherscan module=account&action=txlistinternal (có phân trang)."""
        return self._fetch_all_pages(
            chain, address, incident_id, action="txlistinternal", start_block=start_block, end_block=end_block,
            dedup_key=lambda row: (row.get("hash"), row.get("traceId")),
        )

    def _fetch_all_pages(
        self,
        chain: str,
        address: str,
        incident_id: str,
        action: str,
        start_block: int,
        end_block: int,
        dedup_key,
        page_size: int = 10_000,
        max_windows: int = 200,
    ) -> List[Dict[str, Any]]:
        # Xoá SẠCH mọi file cache cũ của (chain, address, incident_id, action)
        # trước khi fetch lại — bug thật phát hiện 2026-08-14 (rà soát
        # cache/pagination hệ thống, xem annotation_guide.md mục 14): cache
        # trước đây đặt tên theo start_block hiện tại, không đè lên file của
        # 1 lần gọi TRƯỚC với start_block khác (vd cửa sổ rộng hơn khi audit)
        # -> 2+ file window CHỒNG LẤN nhau tồn tại song song,
        # _load_cached_rows gộp cả 2 (dù đã dedup theo hash) làm sai
        # merge_events_into_semantic_actions (thêm leg trùng gần-giống khiến
        # phân loại swap/split sai). Xoá sạch đảm bảo tại mọi thời điểm chỉ
        # có ĐÚNG 1 "thế hệ" cache cho 1 (address, incident_id, action) —
        # phản ánh đúng lần fetch GẦN NHẤT CỦA CHÍNH incident_id này (KHÔNG
        # đụng tới cache của incident_id khác — xem _cache_path, bug #6).
        stale_dir = self.cache_dir / chain / address.lower() / incident_id
        if stale_dir.exists():
            for stale_file in stale_dir.glob(f"{action}_w*_from_*.json"):
                stale_file.unlink()

        all_rows: List[Dict[str, Any]] = []
        seen = set()
        current_start = start_block
        original_start = start_block

        for window_idx in range(max_windows):
            cache_path = self._cache_path(chain, address, incident_id, f"{action}_w{window_idx}", current_start)
            params = {
                "module": "account",
                "action": action,
                "address": address,
                "startblock": current_start,
                "endblock": end_block,
                "page": 1,
                "offset": page_size,
                "sort": "asc",
            }
            payload = self._get(chain, params, cache_path=cache_path)
            rows = self._extract_result_list(payload)

            new_rows = [r for r in rows if dedup_key(r) not in seen]
            for r in new_rows:
                seen.add(dedup_key(r))
            all_rows.extend(new_rows)

            if len(rows) < page_size:
                break  # đã lấy hết record trong [current_start, end_block]

            last_block = int(rows[-1]["blockNumber"])
            if last_block <= current_start:
                # tất cả record còn lại nằm trong cùng 1 block, không thể tiến
                # thêm bằng cách tăng startblock -> dừng để tránh vòng lặp vô hạn.
                break
            current_start = last_block  # trùng lặp ở block biên được lọc bằng dedup_key
        else:
            raise EtherscanAPIError(
                f"Vượt quá max_windows={max_windows} khi phân trang {action} cho {address} "
                f"từ block {original_start} — dữ liệu có thể chưa lấy đủ."
            )

        return all_rows

    @staticmethod
    def _extract_result_list(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        result = payload.get("result")
        if payload.get("status") == "0":
            message = str(payload.get("message", ""))
            # "No transactions found" là kết quả hợp lệ (status=0), không phải lỗi
            if "no transactions found" in message.lower():
                return []
            raise EtherscanAPIError(f"Etherscan API trả lỗi: {payload.get('message')} / {result}")
        if not isinstance(result, list):
            raise EtherscanAPIError(f"Kết quả Etherscan API không phải list: {result!r}")
        return result


# Hàm tiện ích cấp module, dùng client mặc định lấy key từ env mỗi lần gọi.
def fetch_normal_txs(
    chain: str, address: str, incident_id: str, start_block: int = 0, end_block: int = 99_999_999, **client_kwargs
) -> List[Dict[str, Any]]:
    return EtherscanClient(**client_kwargs).fetch_normal_txs(chain, address, incident_id, start_block, end_block)


def fetch_erc20_transfers(
    chain: str, address: str, incident_id: str, start_block: int = 0, end_block: int = 99_999_999, **client_kwargs
) -> List[Dict[str, Any]]:
    return EtherscanClient(**client_kwargs).fetch_erc20_transfers(chain, address, incident_id, start_block, end_block)


def fetch_internal_txs(
    chain: str, address: str, incident_id: str, start_block: int = 0, end_block: int = 99_999_999, **client_kwargs
) -> List[Dict[str, Any]]:
    return EtherscanClient(**client_kwargs).fetch_internal_txs(chain, address, incident_id, start_block, end_block)
