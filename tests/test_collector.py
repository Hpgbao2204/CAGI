"""
Test cho collector Etherscan-family API (Bước 2). KHÔNG gọi mạng thật:
mock requests.Session.get bằng unittest.mock.
"""
import json
from unittest.mock import MagicMock, patch

import pytest

from src.collect.etherscan_client import (
    CHAIN_IDS,
    EtherscanAPIError,
    EtherscanClient,
)

ADDRESS = "0x" + "1" * 40
INCIDENT_ID = "test_incident"


def _mock_response(status_code=200, json_payload=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_payload or {}
    resp.text = text if text is not None else json.dumps(json_payload or {})
    resp.raise_for_status = MagicMock()
    return resp


def test_missing_api_key_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("ETHERSCAN_API_KEY", raising=False)
    with pytest.raises(ValueError):
        EtherscanClient(api_key=None, cache_dir=tmp_path)


def test_fetch_normal_txs_success_and_caches_response(tmp_path):
    session = MagicMock()
    session.get.return_value = _mock_response(
        json_payload={"status": "1", "message": "OK", "result": [{"hash": "0xabc", "blockNumber": "100"}]}
    )
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)

    result = client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID, start_block=0)

    assert result == [{"hash": "0xabc", "blockNumber": "100"}]
    called_params = session.get.call_args.kwargs["params"]
    assert called_params["chainid"] == CHAIN_IDS["eth"]
    assert called_params["apikey"] == "dummy_key"
    assert called_params["module"] == "account"
    assert called_params["action"] == "txlist"

    # Cache SCOPED theo incident_id (bug #6, xem annotation_guide.md mục 14/15) —
    # file nằm dưới {chain}/{address}/{incident_id}/, không phải trực tiếp
    # dưới {chain}/{address}/.
    cache_files = list((tmp_path / "eth" / ADDRESS.lower() / INCIDENT_ID).glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert "checksum_sha256" in cached
    assert "requested_at_utc" in cached
    assert cached["response"]["result"][0]["hash"] == "0xabc"


def test_fetch_erc20_transfers_uses_correct_action(tmp_path):
    session = MagicMock()
    session.get.return_value = _mock_response(json_payload={"status": "1", "message": "OK", "result": []})
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)

    client.fetch_erc20_transfers("bsc", ADDRESS, incident_id=INCIDENT_ID)

    called_params = session.get.call_args.kwargs["params"]
    assert called_params["action"] == "tokentx"
    assert called_params["chainid"] == CHAIN_IDS["bsc"]


def test_fetch_internal_txs_uses_correct_action(tmp_path):
    session = MagicMock()
    session.get.return_value = _mock_response(json_payload={"status": "1", "message": "OK", "result": []})
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)

    client.fetch_internal_txs("arbitrum", ADDRESS, incident_id=INCIDENT_ID)

    called_params = session.get.call_args.kwargs["params"]
    assert called_params["action"] == "txlistinternal"
    assert called_params["chainid"] == CHAIN_IDS["arbitrum"]


def test_no_transactions_found_returns_empty_list(tmp_path):
    session = MagicMock()
    session.get.return_value = _mock_response(
        json_payload={"status": "0", "message": "No transactions found", "result": []}
    )
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)

    result = client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID)
    assert result == []


def test_other_api_error_raises(tmp_path):
    session = MagicMock()
    session.get.return_value = _mock_response(
        json_payload={"status": "0", "message": "Error! Invalid address format", "result": "Error! Invalid address format"}
    )
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)

    with pytest.raises(EtherscanAPIError):
        client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID)


def test_rate_limit_429_then_success_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)  # không sleep thật trong test
    session = MagicMock()
    rate_limited = _mock_response(status_code=429)
    success = _mock_response(json_payload={"status": "1", "message": "OK", "result": []})
    session.get.side_effect = [rate_limited, rate_limited, success]

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session, max_retries=5)
    result = client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID)

    assert result == []
    assert session.get.call_count == 3


def test_rate_limit_message_status_zero_triggers_retry(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    rate_limited = _mock_response(
        json_payload={"status": "0", "message": "Max rate limit reached", "result": None}
    )
    success = _mock_response(json_payload={"status": "1", "message": "OK", "result": []})
    session.get.side_effect = [rate_limited, success]

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)
    result = client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID)

    assert result == []
    assert session.get.call_count == 2


def test_exhausted_retries_raises_etherscan_api_error(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    session.get.return_value = _mock_response(status_code=429)

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session, max_retries=3)
    with pytest.raises(EtherscanAPIError):
        client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID)
    assert session.get.call_count == 3


def test_timeout_retries_then_raises(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    session.get.side_effect = requests.exceptions.Timeout("timed out")

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session, max_retries=2)
    with pytest.raises(EtherscanAPIError):
        client.fetch_normal_txs("eth", ADDRESS, incident_id=INCIDENT_ID)
    assert session.get.call_count == 2


def test_invalid_chain_raises_value_error(tmp_path):
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=MagicMock())
    with pytest.raises(ValueError):
        client.fetch_normal_txs("solana", ADDRESS, incident_id=INCIDENT_ID)


def test_api_key_read_from_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("ETHERSCAN_API_KEY", "env_key_123")
    client = EtherscanClient(cache_dir=tmp_path, session=MagicMock())
    assert client.api_key == "env_key_123"


def test_pagination_advances_startblock_and_aggregates_pages(tmp_path):
    """Khi 1 page trả về đủ page_size record, client phải tự động gọi thêm
    trang tiếp theo (đẩy startblock lên block cuối) thay vì cắt cụt dữ liệu.
    """
    session = MagicMock()

    def make_rows(n, block_start, hash_prefix):
        return [
            {"hash": f"0x{hash_prefix}{i}", "blockNumber": str(block_start + i), "logIndex": "0"}
            for i in range(n)
        ]

    page1_rows = make_rows(3, block_start=100, hash_prefix="a")  # đủ page_size=3 -> phải fetch tiếp
    page2_rows = make_rows(2, block_start=200, hash_prefix="b")  # thiếu page_size -> dừng

    session.get.side_effect = [
        _mock_response(json_payload={"status": "1", "message": "OK", "result": page1_rows}),
        _mock_response(json_payload={"status": "1", "message": "OK", "result": page2_rows}),
    ]

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)
    result = client._fetch_all_pages(
        "eth", ADDRESS, incident_id=INCIDENT_ID, action="txlist", start_block=0, end_block=99_999_999,
        dedup_key=lambda r: (r["hash"],), page_size=3,
    )

    assert len(result) == 5  # 3 + 2, không bị cắt cụt ở mốc 3
    assert session.get.call_count == 2
    second_call_params = session.get.call_args_list[1].kwargs["params"]
    assert second_call_params["startblock"] == 102  # block cuối của page1


def test_pagination_dedups_boundary_transaction(tmp_path):
    """Tx nằm đúng ở block biên (startblock mới) có thể xuất hiện lại ở
    trang kế tiếp — phải bị lọc trùng theo dedup_key, không đếm 2 lần."""
    session = MagicMock()
    page1 = [
        {"hash": "0xaaa", "blockNumber": "100", "logIndex": "0"},
        {"hash": "0xbbb", "blockNumber": "100", "logIndex": "0"},
    ]
    # 0xbbb lặp lại ở block biên 100 vì startblock kế tiếp = 100
    page2 = [{"hash": "0xbbb", "blockNumber": "100", "logIndex": "0"}]

    session.get.side_effect = [
        _mock_response(json_payload={"status": "1", "message": "OK", "result": page1}),
        _mock_response(json_payload={"status": "1", "message": "OK", "result": page2}),
    ]

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)
    result = client._fetch_all_pages(
        "eth", ADDRESS, incident_id=INCIDENT_ID, action="txlist", start_block=0, end_block=99_999_999,
        dedup_key=lambda r: (r["hash"],), page_size=2,
    )
    # page2 có 1 record == 1 < page_size=2 -> dừng sau page2, nhưng 0xbbb bị dedup
    hashes = [r["hash"] for r in result]
    assert hashes.count("0xbbb") == 1
    assert set(hashes) == {"0xaaa", "0xbbb"}


def test_pagination_stops_when_all_remaining_in_same_block(tmp_path):
    """Nếu last_block == current_start (mọi record còn lại dồn vào đúng 1
    block), client phải dừng thay vì lặp vô hạn."""
    session = MagicMock()
    page1 = [{"hash": f"0x{i}", "blockNumber": "100", "logIndex": "0"} for i in range(3)]
    session.get.return_value = _mock_response(json_payload={"status": "1", "message": "OK", "result": page1})

    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)
    result = client._fetch_all_pages(
        "eth", ADDRESS, incident_id=INCIDENT_ID, action="txlist", start_block=100, end_block=99_999_999,
        dedup_key=lambda r: (r["hash"],), page_size=3,
    )
    assert session.get.call_count == 1  # dừng ngay, không lặp vô hạn
    assert len(result) == 3


def test_two_incidents_same_address_different_window_do_not_overwrite(tmp_path):
    """Test BẮT BUỘC theo yêu cầu người dùng (bug #6, xem annotation_guide.md
    mục 15): 2 incident khác nhau fetch CÙNG 1 địa chỉ trong 2 khung thời
    gian khác nhau — cache của 2 incident phải tồn tại ĐỘC LẬP, không cái
    nào ghi đè cái nào, BẤT KỂ thứ tự fetch trước/sau."""
    session = MagicMock()
    session.get.side_effect = [
        _mock_response(json_payload={"status": "1", "message": "OK", "result": [{"hash": "0xincident_a", "blockNumber": "100"}]}),
        _mock_response(json_payload={"status": "1", "message": "OK", "result": [{"hash": "0xincident_b", "blockNumber": "999999"}]}),
    ]
    client = EtherscanClient(api_key="dummy_key", cache_dir=tmp_path, session=session)

    # incident_a fetch TRƯỚC, window [0, 1000]
    result_a = client.fetch_normal_txs("eth", ADDRESS, incident_id="incident_a", start_block=0, end_block=1000)
    # incident_b fetch SAU, window KHÁC [900000, 1000000], CÙNG 1 địa chỉ
    result_b = client.fetch_normal_txs("eth", ADDRESS, incident_id="incident_b", start_block=900_000, end_block=1_000_000)

    assert result_a == [{"hash": "0xincident_a", "blockNumber": "100"}]
    assert result_b == [{"hash": "0xincident_b", "blockNumber": "999999"}]

    # Cả 2 file cache PHẢI còn tồn tại độc lập sau khi cả 2 lần fetch hoàn tất —
    # đọc lại incident_a's cache (không fetch mạng lại) phải vẫn đúng dữ liệu
    # của incident_a, KHÔNG bị incident_b ghi đè.
    dir_a = tmp_path / "eth" / ADDRESS.lower() / "incident_a"
    dir_b = tmp_path / "eth" / ADDRESS.lower() / "incident_b"
    assert dir_a.exists() and dir_b.exists()
    files_a = list(dir_a.glob("*.json"))
    files_b = list(dir_b.glob("*.json"))
    assert len(files_a) == 1
    assert len(files_b) == 1
    cached_a = json.loads(files_a[0].read_text(encoding="utf-8"))
    cached_b = json.loads(files_b[0].read_text(encoding="utf-8"))
    assert cached_a["response"]["result"][0]["hash"] == "0xincident_a"
    assert cached_b["response"]["result"][0]["hash"] == "0xincident_b"

    # Fetch lại incident_a LẦN NỮA (do_collect=True mới, giả lập rebuild) —
    # incident_b's cache vẫn phải nguyên vẹn, không bị đụng tới.
    session.get.side_effect = [
        _mock_response(json_payload={"status": "1", "message": "OK", "result": [{"hash": "0xincident_a_v2", "blockNumber": "150"}]}),
    ]
    client.fetch_normal_txs("eth", ADDRESS, incident_id="incident_a", start_block=0, end_block=1000)
    cached_b_after = json.loads(files_b[0].read_text(encoding="utf-8"))
    assert cached_b_after["response"]["result"][0]["hash"] == "0xincident_b", (
        "incident_b cache bị ảnh hưởng bởi fetch lại của incident_a — bug #6 CHƯA sửa đúng"
    )
