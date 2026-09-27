"""
Test cho collector BSC qua BSCTrace/MegaNode (src/collect/bsctrace_client.py).
KHÔNG gọi mạng thật: mock requests.Session.post.

Mock response dùng ĐÚNG schema thật, xác nhận qua smoke_test() với key thật
ngày 2026-08-13 (địa chỉ QBridge exploiter): value là hex raw base-unit,
blockTimeStamp unix int ở top-level, logIndex có sẵn, phân trang qua
`pageKey` (không phải `pageToken` như tài liệu công khai gợi ý).
"""
import json
from unittest.mock import MagicMock

import pytest

from src.collect.bsctrace_client import (
    BscTraceAPIError,
    BscTraceClient,
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


def _transfer_row(tx_hash="0xabc", from_addr=ADDRESS, to_addr="0x" + "2" * 40, value="0x14d1120d7b160000", category="external", log_index=0):
    return {
        "id": 1,
        "category": category,
        "blockNum": "0x100",
        "hash": tx_hash,
        "from": from_addr,
        "to": to_addr,
        "value": value,  # hex raw base-unit
        "asset": "BNB",
        "contractAddress": "0x" + "0" * 40,
        "blockTimeStamp": 1643320487,
        "logIndex": log_index,
    }


def test_missing_api_key_raises(monkeypatch, tmp_path):
    monkeypatch.delenv("BSCTRACE_API_KEY", raising=False)
    monkeypatch.delenv("MEGANODE_API_KEY", raising=False)
    with pytest.raises(ValueError):
        BscTraceClient(api_key=None, cache_dir=tmp_path)


def test_api_key_read_from_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("BSCTRACE_API_KEY", "env_key_123")
    client = BscTraceClient(cache_dir=tmp_path, session=MagicMock())
    assert client.api_key == "env_key_123"
    assert "env_key_123" in client.base_url


def test_api_key_fallback_meganode_env_var(monkeypatch, tmp_path):
    monkeypatch.delenv("BSCTRACE_API_KEY", raising=False)
    monkeypatch.setenv("MEGANODE_API_KEY", "meganode_key_456")
    client = BscTraceClient(cache_dir=tmp_path, session=MagicMock())
    assert client.api_key == "meganode_key_456"


def test_fetch_asset_transfers_single_page(tmp_path):
    session = MagicMock()
    session.post.return_value = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [_transfer_row()], "pageKey": ""}}
    )
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    rows = client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)
    assert len(rows) == 1
    assert rows[0]["hash"] == "0xabc"

    called_body = session.post.call_args.kwargs["json"]
    assert called_body["method"] == "nr_getAssetTransfers"
    assert called_body["params"][0]["fromAddress"] == ADDRESS

    # Cache SCOPED theo incident_id (bug #6, xem annotation_guide.md mục 15) —
    # file nằm dưới bsc/{address}/{incident_id}/, không phải trực tiếp
    # dưới bsc/{address}/.
    cache_files = list((tmp_path / "bsc" / ADDRESS.lower() / INCIDENT_ID).glob("*.json"))
    assert len(cache_files) == 1
    cached = json.loads(cache_files[0].read_text(encoding="utf-8"))
    assert "checksum_sha256" in cached


def test_fetch_asset_transfers_sends_from_block_to_block_as_hex_when_given(tmp_path):
    session = MagicMock()
    session.post.return_value = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [], "pageKey": ""}}
    )
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    client.fetch_asset_transfers(ADDRESS, INCIDENT_ID, from_block=1000, to_block=2000)

    called_body = session.post.call_args.kwargs["json"]
    assert called_body["params"][0]["fromBlock"] == hex(1000)
    assert called_body["params"][0]["toBlock"] == hex(2000)


def test_fetch_asset_transfers_omits_block_params_when_not_given(tmp_path):
    session = MagicMock()
    session.post.return_value = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [], "pageKey": ""}}
    )
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)

    called_body = session.post.call_args.kwargs["json"]
    assert "fromBlock" not in called_body["params"][0]
    assert "toBlock" not in called_body["params"][0]


def test_fetch_asset_transfers_bidirectional_forwards_block_range(tmp_path):
    session = MagicMock()
    session.post.return_value = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [], "pageKey": ""}}
    )
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    client.fetch_asset_transfers_bidirectional(ADDRESS, INCIDENT_ID, from_block=500, to_block=600)

    for call in session.post.call_args_list:
        params = call.kwargs["json"]["params"][0]
        assert params["fromBlock"] == hex(500)
        assert params["toBlock"] == hex(600)


def test_fetch_asset_transfers_paginates_with_page_key(tmp_path):
    session = MagicMock()
    page1 = _mock_response(
        json_payload={
            "jsonrpc": "2.0", "id": 1,
            "result": {"transfers": [_transfer_row(tx_hash="0xaaa")], "pageKey": "next123"},
        }
    )
    page2 = _mock_response(
        json_payload={
            "jsonrpc": "2.0", "id": 1,
            "result": {"transfers": [_transfer_row(tx_hash="0xbbb")], "pageKey": ""},
        }
    )
    session.post.side_effect = [page1, page2]
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    rows = client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)
    assert [r["hash"] for r in rows] == ["0xaaa", "0xbbb"]
    assert session.post.call_count == 2
    second_body = session.post.call_args_list[1].kwargs["json"]
    assert second_body["params"][0]["pageKey"] == "next123"


def test_rpc_error_field_raises(tmp_path):
    session = MagicMock()
    session.post.return_value = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message": "invalid address"}}
    )
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)
    with pytest.raises(BscTraceAPIError):
        client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)


def test_rate_limit_error_message_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    rate_limited = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "error": {"code": 429, "message": "Rate limit exceeded"}}
    )
    success = _mock_response(
        json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [], "pageKey": ""}}
    )
    session.post.side_effect = [rate_limited, success]
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    rows = client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)
    assert rows == []
    assert session.post.call_count == 2


def test_http_429_retries(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = [
        _mock_response(status_code=429),
        _mock_response(json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [], "pageKey": ""}}),
    ]
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)
    rows = client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)
    assert rows == []
    assert session.post.call_count == 2


def test_exhausted_retries_raises(tmp_path, monkeypatch):
    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.return_value = _mock_response(status_code=429)
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session, max_retries=3)
    with pytest.raises(BscTraceAPIError):
        client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)
    assert session.post.call_count == 3


def test_timeout_retries_then_raises(tmp_path, monkeypatch):
    import requests

    monkeypatch.setattr("time.sleep", lambda *_: None)
    session = MagicMock()
    session.post.side_effect = requests.exceptions.Timeout("timed out")
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session, max_retries=2)
    with pytest.raises(BscTraceAPIError):
        client.fetch_asset_transfers(ADDRESS, INCIDENT_ID)
    assert session.post.call_count == 2


def test_fetch_bidirectional_merges_and_dedups(tmp_path):
    session = MagicMock()
    out_row = _transfer_row(tx_hash="0xout1", from_addr=ADDRESS, to_addr="0x" + "9" * 40, log_index=1)
    in_row = _transfer_row(tx_hash="0xin1", from_addr="0x" + "8" * 40, to_addr=ADDRESS, log_index=2)
    dup_row = dict(out_row)  # đại diện trường hợp bị lặp giữa 2 lần gọi (cùng hash+category+logIndex)

    responses = [
        _mock_response(json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [out_row], "pageKey": ""}}),
        _mock_response(json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [in_row, dup_row], "pageKey": ""}}),
    ]
    session.post.side_effect = responses
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    rows = client.fetch_asset_transfers_bidirectional(ADDRESS, INCIDENT_ID)
    hashes = sorted(r["hash"] for r in rows)
    assert hashes == ["0xin1", "0xout1"]  # dup_row bị loại


def test_two_incidents_same_address_different_window_do_not_overwrite(tmp_path):
    """Test BẮT BUỘC theo yêu cầu người dùng (bug #6, xem annotation_guide.md
    mục 15) — bản BSCTrace: 2 incident khác nhau fetch CÙNG 1 địa chỉ với 2
    khung thời gian khác nhau — cache của 2 incident phải tồn tại ĐỘC LẬP,
    không cái nào ghi đè cái nào, BẤT KỂ thứ tự fetch trước/sau."""
    session = MagicMock()
    session.post.side_effect = [
        _mock_response(json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [_transfer_row(tx_hash="0xincident_a")], "pageKey": ""}}),
        _mock_response(json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [_transfer_row(tx_hash="0xincident_b")], "pageKey": ""}}),
    ]
    client = BscTraceClient(api_key="dummy", cache_dir=tmp_path, session=session)

    result_a = client.fetch_asset_transfers(ADDRESS, "incident_a", from_block=0, to_block=1000)
    result_b = client.fetch_asset_transfers(ADDRESS, "incident_b", from_block=900_000, to_block=1_000_000)

    assert result_a[0]["hash"] == "0xincident_a"
    assert result_b[0]["hash"] == "0xincident_b"

    dir_a = tmp_path / "bsc" / ADDRESS.lower() / "incident_a"
    dir_b = tmp_path / "bsc" / ADDRESS.lower() / "incident_b"
    assert dir_a.exists() and dir_b.exists()
    files_b_before = list(dir_b.glob("*.json"))
    assert len(files_b_before) == 1
    cached_b_before = json.loads(files_b_before[0].read_text(encoding="utf-8"))
    assert cached_b_before["response"]["result"]["transfers"][0]["hash"] == "0xincident_b"

    # Fetch lại incident_a LẦN NỮA — incident_b's cache phải nguyên vẹn.
    session.post.side_effect = [
        _mock_response(json_payload={"jsonrpc": "2.0", "id": 1, "result": {"transfers": [_transfer_row(tx_hash="0xincident_a_v2")], "pageKey": ""}}),
    ]
    client.fetch_asset_transfers(ADDRESS, "incident_a", from_block=0, to_block=1000)
    cached_b_after = json.loads(files_b_before[0].read_text(encoding="utf-8"))
    assert cached_b_after["response"]["result"]["transfers"][0]["hash"] == "0xincident_b", (
        "incident_b cache bị ảnh hưởng bởi fetch lại của incident_a — bug #6 CHƯA sửa đúng"
    )
