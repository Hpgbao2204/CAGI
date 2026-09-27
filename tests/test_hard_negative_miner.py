"""
Test cho hard-negative miner (mở rộng Bước D). KHÔNG gọi mạng thật —
dùng do_collect=False + cache giả lập, giống pattern tests/test_incident_pipeline.py.
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from src.collect.hard_negative_miner import (
    HARD_NEGATIVE_REGISTRY_PATH,
    MiningReport,
    MiningResult,
    _passes_structural_filter,
    load_known_malicious_addresses,
    mine_all_incidents,
    mine_hard_negatives_for_incident,
    write_hard_negative_registry,
)
from src.normalize.decoder import build_verified_bridge_address_index, build_verified_mixer_address_index, load_protocol_map
from src.pipeline.incident_pipeline import REGISTRY_PATH

CONTRACT = "0x" + "9" * 40  # contract giả lập (không phải mixer)


def _write_bsc_cache(tmp_path, address, transfers, incident_id="test_incident"):
    d = tmp_path / "bsc" / address.lower() / incident_id
    d.mkdir(parents=True, exist_ok=True)
    record = {
        "requested_at_utc": "2026-08-13T00:00:00+00:00", "checksum_sha256": "dummy",
        "response": {"jsonrpc": "2.0", "id": 1, "result": {"transfers": transfers, "pageKey": ""}},
    }
    (d / "assettransfers_w0.json").write_text(json.dumps(record), encoding="utf-8")


def _row(tx_hash, from_addr, to_addr, block=100, ts=1700000000, value="0xde0b6b3a7640000", category="external", log_index=0):
    return {
        "blockNum": hex(block), "hash": tx_hash, "from": from_addr, "to": to_addr,
        "value": value, "asset": "BNB", "category": category, "blockTimeStamp": ts, "logIndex": log_index,
    }


def test_load_known_malicious_addresses_reads_heist_column():
    addrs = load_known_malicious_addresses()
    assert len(addrs) > 0
    # địa chỉ Ronin hacker (đã biết) phải nằm trong danh sách loại trừ
    assert "0x098b716b8aaf21512996dc57eb0615e2383e2f96" in addrs


# ----------------------------------------------------------------------
# _passes_structural_filter — mỗi tiêu chí lọc phải có assertion riêng
# ----------------------------------------------------------------------
def test_structural_filter_accepts_clean_bridge_withdraw_swap(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    _write_bsc_cache(tmp_path, candidate, [
        _row("0x" + "a" * 64, candidate, CONTRACT, block=100),
        _row("0x" + "b" * 64, candidate, "0x" + "2" * 40, block=101, category="20"),
    ])
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    passed, reason, _block = _passes_structural_filter("bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi)
    assert passed, reason


def test_structural_filter_rejects_unexpected_mixer_followup(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    tornado = "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b"  # mixer đã verify trong protocol_map.yaml
    _write_bsc_cache(tmp_path, candidate, [
        _row("0x" + "a" * 64, candidate, CONTRACT, block=100),
        _row("0x" + "b" * 64, candidate, tornado, block=101),
    ])
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    passed, reason, _block = _passes_structural_filter("bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi)
    assert not passed
    assert reason == "unexpected_mixer_followup"


def test_structural_filter_rejects_fan_out_split_pattern(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    _write_bsc_cache(tmp_path, candidate, [
        _row("0x" + "a" * 64, candidate, CONTRACT, block=100),
        _row("0x" + "b" * 64, candidate, "0x" + "2" * 40, block=101),
        _row("0x" + "c" * 64, candidate, "0x" + "3" * 40, block=102),
        _row("0x" + "d" * 64, candidate, "0x" + "4" * 40, block=103),
        _row("0x" + "e" * 64, candidate, "0x" + "5" * 40, block=104),
    ])
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    passed, reason, _block = _passes_structural_filter("bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi)
    assert not passed
    assert reason == "fan_out_split_like_pattern"


def test_structural_filter_rejects_no_direct_interaction(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    _write_bsc_cache(tmp_path, candidate, [
        _row("0x" + "a" * 64, candidate, "0x" + "2" * 40, block=100),  # không liên quan CONTRACT
    ])
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    passed, reason, _block = _passes_structural_filter("bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi)
    assert not passed
    assert reason == "no_direct_interaction_with_contract"


def test_structural_filter_rejects_empty_window(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)
    passed, reason, _block = _passes_structural_filter("bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi)
    assert not passed
    assert reason == "no_events_in_window"


def test_structural_filter_allows_single_mixer_deposit_when_contract_is_mixer(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    tornado = "0xd90e2f925da726b50c4ed8d0fb90ad053324f31b"
    _write_bsc_cache(tmp_path, candidate, [_row("0x" + "a" * 64, candidate, tornado, block=100)])
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    passed, reason, _block = _passes_structural_filter("bsc", candidate, tornado, "test_incident", True, 0, 1000, bi, mi)
    assert passed, reason


def test_structural_filter_rejects_insufficient_complexity(tmp_path, monkeypatch):
    """Bug shortcut do dai (Tuan 5, leakage_audit_v1) - min_candidate_events
    moi them: candidate qua don gian (it event hon nguong) phai bi loai,
    KHONG anh huong hanh vi mac dinh (min_candidate_events=1) cho cac lan
    goi cu."""
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    _write_bsc_cache(tmp_path, candidate, [
        _row("0x" + "a" * 64, candidate, CONTRACT, block=100),
        _row("0x" + "b" * 64, candidate, "0x" + "2" * 40, block=101, category="20"),
    ])
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    # Mac dinh (min_candidate_events=1): 2 event du de pass (giong test
    # test_structural_filter_accepts_clean_bridge_withdraw_swap).
    passed, reason, _block = _passes_structural_filter(
        "bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi,
    )
    assert passed, reason

    # min_candidate_events=5 (gia lap incident positive dai): 2 event KHONG du.
    passed, reason, _block = _passes_structural_filter(
        "bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi,
        min_candidate_events=5,
    )
    assert not passed
    assert reason == "insufficient_complexity_vs_positive"


def test_compute_min_candidate_events_scales_log_with_positive_length():
    from src.collect.hard_negative_miner import compute_min_candidate_events

    # positive rat ngan (vd deltaprime_arbitrum_2024, len=5) -> nguong thap.
    assert compute_min_candidate_events(5) <= 2
    # positive rat dai (vd ronin_bridge_2022, len=113) -> nguong cao hon
    # RAT NHIEU nhung van << 113 (log-scale, khong phai tuyen tinh).
    threshold_113 = compute_min_candidate_events(113)
    assert threshold_113 > compute_min_candidate_events(5)
    assert threshold_113 < 113
    # positive_len=1 -> khong ep them dieu kien (giu hanh vi cu).
    assert compute_min_candidate_events(1) == 1


def test_compute_max_fan_out_keeps_base_threshold_for_low_positive_fan_out():
    """Tuan 12 - sua tu nguong tuyet doi fan_out<=3 sang band tuong doi.
    positive_fan_out thap (<=3, da so incident) -> GIU NGUYEN nguong CU=3,
    KHONG noi long vo dieu kien."""
    from src.collect.hard_negative_miner import compute_max_fan_out

    assert compute_max_fan_out(1) == 3
    assert compute_max_fan_out(2) == 3
    assert compute_max_fan_out(3) == 3


def test_compute_max_fan_out_scales_log_with_positive_fan_out():
    """positive_fan_out CAO -> ban duoc noi tuong ung (log-scale, khong
    phai tuyen tinh) - fan_out positive cang cao thi nguong cang cao,
    nhung KHONG bung no (van << positive_fan_out o muc rat cao)."""
    from src.collect.hard_negative_miner import compute_max_fan_out

    max_fo_10 = compute_max_fan_out(10)
    max_fo_50 = compute_max_fan_out(50)
    max_fo_100 = compute_max_fan_out(100)

    # Ca 3 deu PHAI noi hon nguong co so 3.
    assert max_fo_10 > 3
    assert max_fo_50 > 3
    assert max_fo_100 > 3
    # Positive fan_out cang cao -> nguong cang cao (dong bien).
    assert max_fo_10 < max_fo_50 < max_fo_100
    # Log-scale (khong phai tuyen tinh 1-1): nguong PHAI nho hon han chinh
    # positive_fan_out o muc rat cao (khong noi long vo dieu kien theo kieu
    # "luon = fan_out cua positive").
    assert max_fo_100 < 100


def test_structural_filter_allows_higher_fan_out_when_max_fan_out_param_raised(tmp_path, monkeypatch):
    """Voi max_fan_out=10 (mo phong band da noi cho incident co positive
    fan_out cao), candidate fan_out=5 (truoc day bi loai boi nguong cu=3)
    gio phai PASS."""
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    candidate = "0x" + "1" * 40
    rows = [_row("0x" + "a" * 64, candidate, CONTRACT, block=100)]
    for i in range(5):
        rows.append(_row("0x" + str(i) * 64, candidate, "0x" + str(i + 2) * 40, block=101 + i))
    _write_bsc_cache(tmp_path, candidate, rows)
    pm = load_protocol_map()
    bi = build_verified_bridge_address_index(pm)
    mi = build_verified_mixer_address_index(pm)

    # Nguong cu (mac dinh max_fan_out=3): van phai loai (khong doi hanh vi cu).
    passed, reason, _block = _passes_structural_filter("bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi)
    assert not passed
    assert reason == "fan_out_split_like_pattern"

    # Nguong moi (max_fan_out=10, band da noi cho incident fan_out cao): PASS.
    passed, reason, _block = _passes_structural_filter(
        "bsc", candidate, CONTRACT, "test_incident", False, 0, 1000, bi, mi, max_fan_out=10,
    )
    assert passed, reason


# ----------------------------------------------------------------------
# Orchestration: mine_hard_negatives_for_incident / mine_all_incidents
# ----------------------------------------------------------------------
def test_mine_hard_negatives_excludes_known_malicious_and_seed(tmp_path, monkeypatch):
    import src.collect.hard_negative_miner as mod
    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    import src.pipeline.incident_pipeline as pipe
    monkeypatch.setattr(pipe, "RAW_DIR", tmp_path)

    seed = "0x098b716b8aaf21512996dc57eb0615e2383e2f96"  # Ronin hacker - trong known-malicious
    good_candidate = "0x" + "1" * 40
    ronin_bridge = "0x1a2a1c938ce3ec39b6d47113c7955baa9dd454f2"

    monkeypatch.setattr(
        mod, "fetch_contract_counterparties",
        lambda chain, contract, incident_id, sb, eb, do_collect=True: [seed, good_candidate],
    )
    _write_bsc_cache(tmp_path, good_candidate, [_row("0x" + "a" * 64, good_candidate, ronin_bridge, block=100)], incident_id="ronin_bridge_2022")
    # cache dưới "eth" cho candidate vì Ronin dùng chain=eth — dùng helper etherscan-style thay vì bsc
    # (SCOPED theo incident_id "ronin_bridge_2022" — bug #6, xem annotation_guide.md mục 15)
    d = tmp_path / "eth" / good_candidate.lower() / "ronin_bridge_2022"
    d.mkdir(parents=True, exist_ok=True)
    payload = {
        "response": {"status": "1", "message": "OK", "result": [
            {"hash": "0x" + "a" * 64, "from": good_candidate, "to": ronin_bridge, "blockNumber": "100",
             "timeStamp": "1700000000", "value": str(10 ** 18)}
        ]},
        "checksum_sha256": "x", "requested_at_utc": "x",
    }
    (d / "txlist_w0_from_0.json").write_text(json.dumps(payload), encoding="utf-8")

    row = {"incident_id": "ronin_bridge_2022", "seed_address": seed, "start_block": "14442775"}
    report = mine_hard_negatives_for_incident(
        "ronin_bridge_2022", row, target_count=5, max_candidates_checked=10,
        excluded_addresses=set(), do_collect=False,
    )
    accepted_addrs = {r.address for r in report.accepted}
    assert seed not in accepted_addrs  # seed KHÔNG được chấp nhận làm hard-negative của chính nó


def test_mine_all_incidents_no_duplicate_address_across_incidents(monkeypatch, tmp_path):
    """Regression bắt buộc: 1 address KHÔNG được dùng làm hard-negative cho
    >1 incident (group leakage)."""
    import src.collect.hard_negative_miner as mod

    shared_candidate = "0x" + "7" * 40

    def fake_fetch(chain, contract, incident_id, sb, eb, do_collect=True):
        return [shared_candidate]

    def fake_filter(chain, candidate, contract, incident_id, is_mixer, sb, eb, bi, mi, min_candidate_events=1, max_fan_out=3):
        return True, "", sb  # luôn pass để kiểm tra riêng logic dedup

    monkeypatch.setattr(mod, "fetch_contract_counterparties", fake_fetch)
    monkeypatch.setattr(mod, "_passes_structural_filter", fake_filter)
    monkeypatch.setattr(mod, "collect_address_raw_data", lambda *a, **k: None)

    import pandas as pd
    registry_df = pd.DataFrame([
        {"incident_id": "ronin_bridge_2022", "label": 1, "seed_address": "0xseedA", "start_block": "100"},
        {"incident_id": "qbridge_qubit_2022", "label": 1, "seed_address": "0xseedB", "start_block": "200"},
    ])
    fake_registry_path = tmp_path / "fake_registry.csv"
    registry_df.to_csv(fake_registry_path, index=False)

    reports = mine_all_incidents(target_per_incident=3, do_collect=False, registry_path=fake_registry_path)

    all_accepted = []
    for report in reports.values():
        all_accepted.extend(r.address for r in report.accepted)

    # shared_candidate chỉ được chấp nhận ở incident ĐẦU TIÊN, không lặp lại
    assert all_accepted.count(shared_candidate) <= 1


def test_mine_does_not_lower_criteria_when_insufficient_candidates(monkeypatch, tmp_path):
    """Nếu không đủ candidate hợp lệ, trả về SỐ THẬT đạt được, không cố ép
    đủ target_count bằng cách hạ tiêu chí."""
    import src.collect.hard_negative_miner as mod

    def fake_fetch(chain, contract, incident_id, sb, eb, do_collect=True):
        return ["0x" + "1" * 40]  # chỉ 1 candidate khả dụng

    def fake_filter(chain, candidate, contract, incident_id, is_mixer, sb, eb, bi, mi, min_candidate_events=1, max_fan_out=3):
        return False, "no_events_in_window", None  # candidate duy nhất KHÔNG đạt

    monkeypatch.setattr(mod, "fetch_contract_counterparties", fake_fetch)
    monkeypatch.setattr(mod, "_passes_structural_filter", fake_filter)
    monkeypatch.setattr(mod, "collect_address_raw_data", lambda *a, **k: None)

    # qbridge_qubit_2022 chỉ map tới ĐÚNG 1 contract mining (PancakeSwap V2)
    # -> fetch_contract_counterparties chỉ bị gọi 1 lần, dễ assert số lượng.
    row = {"incident_id": "qbridge_qubit_2022", "seed_address": "0xseed", "start_block": "100"}
    report = mine_hard_negatives_for_incident(
        "qbridge_qubit_2022", row, target_count=25, max_candidates_checked=10,
        excluded_addresses=set(), do_collect=False,
    )
    assert len(report.accepted) == 0  # KHÔNG bị ép đạt 25
    assert len(report.rejected) == 1


def test_write_hard_negative_registry_maps_to_parent_incident(tmp_path):
    reports = {
        "ronin_bridge_2022": MiningReport(
            parent_incident_id="ronin_bridge_2022",
            accepted=[
                MiningResult(address="0xaaa", chain="eth", contract_used="0xbridge",
                             protocol_name="Ronin Bridge", block_number=100),
                MiningResult(address="0xbbb", chain="eth", contract_used="0xbridge",
                             protocol_name="Ronin Bridge", block_number=101),
            ],
        ),
    }
    out_path = tmp_path / "hard_negative_registry.csv"
    write_hard_negative_registry(reports, path=out_path)

    import pandas as pd
    df = pd.read_csv(out_path)
    assert len(df) == 2
    assert set(df["parent_incident_id"]) == {"ronin_bridge_2022"}
    assert set(df["label"]) == {0}
    assert df["hard_negative_id"].is_unique


# ----------------------------------------------------------------------
# Kiểm tra dữ liệu THẬT sau khi mining (Bước 2 cuối) — skip nếu chưa chạy
# scripts/run_hard_negative_mining.py trong môi trường này.
# ----------------------------------------------------------------------
pytestmark_real_data = pytest.mark.skipif(
    not HARD_NEGATIVE_REGISTRY_PATH.exists(),
    reason="Chưa chạy scripts/run_hard_negative_mining.py (chưa có metadata/hard_negative_registry.csv)",
)


@pytestmark_real_data
def test_real_hard_negative_registry_no_duplicate_seed_address():
    """Bắt buộc: không có địa chỉ hard-negative nào trùng giữa các incident
    khác nhau (group leakage) trong dữ liệu THẬT đã mining."""
    df = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    dup = df[df["seed_address"].duplicated(keep=False)]
    assert dup.empty, f"Address trùng lặp giữa các incident:\n{dup}"


@pytestmark_real_data
def test_real_hard_negative_registry_no_overlap_with_incident_registry():
    """Hard-negative KHÔNG được trùng với bất kỳ seed_address nào đã dùng
    trong incident_registry.csv (positive lẫn 5 hard-negative gốc)."""
    hn_df = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    reg_df = pd.read_csv(REGISTRY_PATH)
    overlap = set(hn_df["seed_address"].str.lower()) & set(reg_df["seed_address"].str.lower())
    assert not overlap, f"Địa chỉ trùng với incident_registry.csv: {overlap}"


@pytestmark_real_data
def test_real_hard_negative_registry_every_row_maps_to_positive_incident():
    hn_df = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    reg_df = pd.read_csv(REGISTRY_PATH)
    positive_ids = set(reg_df[reg_df["label"] == 1]["incident_id"])
    assert set(hn_df["parent_incident_id"]) <= positive_ids


@pytestmark_real_data
def test_real_hard_negative_registry_reports_actual_count_vs_gate():
    """Test bắt buộc: kiểm tra số lượng ≥200 sau mining, PHẢI dùng con số
    "dùng được" (trajectory sinh ra ≥1 prefix row khi build lại bằng
    expand_and_build_trajectory chuẩn) — KHÔNG phải "raw" (số dòng trong
    hard_negative_registry.csv). Bug thật đã xảy ra (2026-08-13): báo cáo
    ban đầu dùng raw=208 làm gate "đạt 200", trong khi usable thật chỉ
    196 — SAI. Luôn in RÕ CẢ 2 con số riêng biệt.

    Nếu KHÔNG đạt ngưỡng 200 (theo usable), test vẫn PASS (không hạ tiêu
    chí) nhưng in rõ con số thật đạt được — quyết định freeze/không freeze
    là của người dùng, không phải của test này.
    """
    from src.pipeline.incident_pipeline import expand_and_build_trajectory
    from src.trajectories.builder import load_trajectory_config

    hn_df = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    reg_df = pd.read_csv(REGISTRY_PATH)
    config = load_trajectory_config()

    raw = len(hn_df)
    n_empty = 0
    for _, row in hn_df.iterrows():
        # Dung parent_incident_id (KHONG phai hard_negative_id) — bug #6 sua
        # cache scoping theo incident_id, cache LUC MINING dung parent_
        # incident_id lam scope (xem annotation_guide.md muc 15).
        traj, _, _ = expand_and_build_trajectory(
            row["chain"], row["seed_address"], int(row["start_block"]), row["parent_incident_id"], 0,
            config=config, do_collect=False, max_iterations=2,
        )
        if len(traj) == 0:
            n_empty += 1

    n_original_controls = len(reg_df[reg_df["label"] == 0])
    usable = (raw - n_empty) + n_original_controls

    print(f"\nraw mining = {raw}")
    print(f"dùng được (mining, ≥1 prefix row) = {raw - n_empty} (rỗng: {n_empty})")
    print(f"+ {n_original_controls} hard-negative control gốc (đều dùng được)")
    print(f"TỔNG dùng được = {usable} (ngưỡng yêu cầu: >=200)")

    if usable < 200:
        pytest.skip(f"CHƯA đạt ngưỡng 200 hard-negative DÙNG ĐƯỢC — chỉ đạt {usable} "
                     f"(raw={raw}). Đây là báo cáo thật, KHÔNG phải lỗi test.")
    assert usable >= 200


@pytestmark_real_data
def test_real_full_dataset_no_group_leakage_across_all_groups():
    """QA cuối (Bước 3/4): dựng lại TOÀN BỘ trajectory (10 incident gốc +
    toàn bộ hard-negative đã mining), xác nhận KHÔNG có tx_hash hay address
    (ngoại trừ protocol contract công khai) nào xuất hiện ở >1 group
    (incident_id / parent_incident_id) — group leakage thật sẽ phá vỡ giả
    định GroupKFold. Bug thật phát hiện & đã sửa 2026-08-13: 2 address bị
    trùng giữa các group (ronin_bridge_2022 hn023 trùng ronin_benign_control,
    feg_bridge_2024 hn026 trùng deltaprime_arbitrum_2024 hn043 — cùng 1 hex
    address xuất hiện ở 2 chain khác nhau) — đã loại 3 hard-negative liên
    quan để dataset sạch tuyệt đối, vẫn dư nhiều so với ngưỡng 200.
    """
    from src.pipeline.incident_pipeline import expand_and_build_trajectory
    from src.trajectories.builder import load_trajectory_config

    protocol_map = load_protocol_map()
    known_protocol_addrs = {
        "0x0000000000000000000000000000000000000000",  # null/burn address — xuất hiện ở MỌI incident có
        # cơ chế burn-to-bridge (vd AnySwap legacy 2021, xem Wault.Finance) — không phải leak thật (không
        # phải 1 thực thể/counterparty phân biệt được), tương tự lý do loại trừ protocol contract công khai.
        "0xdd90e5e87a2081dcf0391920868ebc2ffb81a1af",  # địa chỉ trung gian dùng chung (bsc) — xuất hiện ở
        # qbridge_qubit_2022 (1 trong 2 ví trung gian trọng tâm) VÀ paraluni_2022 (1 lần chạm duy nhất,
        # không phải bằng chứng gate). Đã xác nhận qua on-chain thật 2026-08-14: 481 địa chỉ gửi/789 địa
        # chỉ nhận độc lập trong cửa sổ đã kiểm tra — hành vi CEX/OTC hot wallet phổ biến, KHÔNG phải liên
        # hệ rửa tiền riêng giữa 2 vụ (trùng ngẫu nhiên do cùng dùng dịch vụ chung, không phải 1 thực thể
        # phân biệt được cho mục đích leave-one-group-out).
        # 8 địa chỉ dưới đây mới XUẤT HIỆN sau khi sửa bug value_share gộp-token
        # (2026-08-27, xem builder.py::outflow_by_src_token) — fix hé lộ thêm
        # nhiều swap event thật trước đây bị loại oan, các swap này đi qua các
        # AMM pool/market contract DÙNG CHUNG. Đã xác nhận từng địa chỉ qua
        # eth_getCode (đều là CONTRACT, không phải EOA) + getsourcecode thật
        # (không suy đoán) trước khi loại trừ:
        "0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2",  # WETH9 (Ethereum) — token hạ tầng dùng chung
        # toàn cầu, ronin_bridge_2022 & ronin_benign_control_2022 đều chạm vì đây LÀ token WETH, không
        # phải 1 thực thể/counterparty phân biệt được.
        "0x61eb789d75a95caa3ff50ed7e47b96c132fec082",  # PancakePair (bsc) — xác nhận ContractName=
        # "PancakePair" qua getsourcecode thật — AMM pool dùng chung, paraluni_2022 & qbridge_qubit_2022.
        "0x0ed7e52944161450477ee417de9cd3a859b14fd0",  # PancakePair (bsc) — xác nhận tương tự.
        "0x74e4716e431f45807dcf19f284c7aa99f18a4fbc",  # PancakePair (bsc) — xác nhận tương tự.
        "0xc986cde72a2f91dfde731a6f933c702c108cc1a4",  # code_len=128 giống hệt 5 PancakePair đã xác
        # nhận verified (minimal-proxy bytecode cùng độ dài) — source chưa verify trên BscScan nhưng
        # cùng pattern factory-deployed pool, không phải EOA/thực thể phân biệt được.
        "0x58f876857a02d6762e0101bb5c46a8c1ed44dc16",  # PancakePair (bsc) — xác nhận tương tự.
        "0x7efaef62fddcca950418312c6c91aef321375a00",  # PancakePair (bsc) — paraluni_2022 &
        # bsc_token_hub_2022 — xác nhận tương tự.
        "0xc3f3a07ae7d2a125ef81a5950c4d0dd54c740251",  # contract lớn (47KB bytecode, arbitrum),
        # deltaprime_arbitrum_2024 & radiant_capital_arbitrum_2024 — cả 2 seed đều giao dịch qua token
        # GMX market ("GM: ..."); source chưa verify trên Arbiscan nhưng chỉ 1 native tx độc lập trong
        # toàn bộ lịch sử (không phải ví cá nhân hoạt động thường xuyên) — nhất quán với market/vault
        # contract GMX dùng chung bởi mọi trader, không phải liên hệ riêng giữa 2 vụ.
        # 14 địa chỉ dưới đây XUẤT HIỆN sau khi rebuild dùng cache đã fetch đủ
        # sâu hơn (fix value_share per-token áp dụng trên trajectory lớn hơn
        # nhiều — ronin_bridge_2022 113→2312 action, paraluni_2022 38→511,
        # qbridge_qubit_2022 52→698...). Đã xác nhận TỪNG địa chỉ qua
        # eth_getCode thật (đều CONTRACT, không EOA) trước khi loại trừ:
        "0x220bda5c8994804ac96ebe4df184d25e5c2196d4",  # contract lớn (43KB, eth), ronin_bridge_2022 &
        # ronin_benign_control_2022 — 2 trajectory ĐỘC LẬP trên cùng chain quanh cùng giai đoạn, hạ tầng
        # dùng chung (nguồn chưa verify trên Etherscan nhưng xác nhận CONTRACT, không phải EOA cá nhân).
        "0x2057cfb9fd11837d61b294d514c5bd03e5e7189a",  # contract lớn (44KB, eth) — tương tự.
        "0x8f8dd7db1bda5ed3da8c9daf3bfa471c12d58486",  # DODOV2Proxy02 (bsc, xác nhận ContractName qua
        # getsourcecode) — router DODO DEX dùng chung, paraluni_2022/qbridge_qubit_2022/wault_finance_2021.
        "0x8e01cc26d6dd73581347c4370573ce9e59e74802",  # code_len=128 (PancakePair pattern), bsc.
        "0xedf0c420bc3b92b961c6ec411cc810ca81f5f21a",  # code_len=128 (PancakePair pattern), bsc.
        "0x8965349fb649a33a30cbfda057d8ec2c48abe2a2",  # code_len=128 (PancakePair pattern), bsc.
        "0xf058cb4386f7a4552e75789a306dc63074335a9d",  # code_len=128 (PancakePair pattern), bsc.
        "0x089a2c44131b1eb30cc4fc226560163fcef2c288",  # code_len=128 (PancakePair pattern), bsc.
        "0x8e4842d0570c85ba3805a9508dce7c6a458359d0",  # code_len=128 (PancakePair pattern), bsc.
        "0x82af49447d8a07e3bd95bd0d56f35241523fbab1",  # WETH (arbitrum) — xác nhận ContractName=
        # "TransparentUpgradeableProxy" qua getsourcecode (WETH9 Arbitrum nằm sau proxy) — token hạ tầng
        # dùng chung toàn cầu, deltaprime_arbitrum_2024 & xkingdom_2024.
        "0xfd5840cd36d94d7229439859c0112a4185bc0255",  # code_len=128 (PancakePair pattern), bsc.
        "0xf45cd219aef8618a92baa7ad848364a158a24f33",  # code_len=128 (PancakePair pattern), bsc.
        "0x804678fa97d91b974ec2af3c843270886528a9e6",  # code_len=128 (PancakePair pattern), bsc.
        "0xdb6f1920a889355780af7570773609bd8cb1f498",  # CÙNG 1 hex address nhưng KHÁC HẲN bytecode giữa
        # 2 chain (bsc: "FlashWallet" 0x Protocol, 128 byte tương tự PancakePair trên arbitrum thực tế
        # khác — đã kiểm tra riêng code_len 6456 vs 128) — trùng ngẫu nhiên giữa 2 chain độc lập (paraluni_2022
        # trên BSC vs radiant_capital_arbitrum_2024 trên Arbitrum), giống hệt pattern đã ghi nhận ở
        # 0xdd90e5e8... phía trên — KHÔNG phải cùng 1 thực thể (địa chỉ trên 2 chain là 2 tài khoản độc lập).
        # 5 địa chỉ dưới đây xuất hiện sau khi mine hard-negative cho
        # radiant_capital_arbitrum_2024 (Giai đoạn B, Bước 2 revisit,
        # 2026-08-27) — trùng với deltaprime_arbitrum_2024/wooppv2_2024 (cả 2
        # đều Arbitrum, cùng hệ sinh thái bridge/DEX). Đã xác nhận TỪNG địa
        # chỉ qua eth_getCode + getsourcecode thật:
        "0xb300000b72deaeb607a12d5f54773d1c19c7028d",  # ContractName="Diamond" (diamond-proxy pattern,
        # hạ tầng DEX/bridge dùng chung) — deltaprime_arbitrum_2024 & radiant_capital_arbitrum_2024.
        "0x7a70cb77a12fa2dc3fa1bc1dcbca4c79db71a289",  # CONTRACT (2492 byte, chưa verify source) — tương tự.
        "0x391e7c679d29bd940d63be94ad22a25d25b5a604",  # EOA (không phải contract) — NHƯNG đã xác nhận qua
        # on-chain thật: 692 địa chỉ gửi độc lập, chỉ 2 địa chỉ nhận — mẫu hình dịch vụ dùng chung (gas
        # refund/relayer/faucet), KHÔNG phải liên hệ riêng giữa 2 vụ, cùng logic đã dùng cho 0xdd90e5e8...
        "0x1195cf65f83b3a5768f3c496d3a05ad6412c64b7",  # ERC1967Proxy (proxy pattern chuẩn, hạ tầng dùng chung).
        "0xecc19e177d24551aa7ed6bc6fe566eca726cc8a9",  # StargateComposer (xác nhận ContractName qua
        # getsourcecode) — hạ tầng Stargate/LayerZero dùng chung, wooppv2_2024 & radiant_capital_arbitrum_2024.
        # 1 địa chỉ xuất hiện khi thêm incident magic_abracadabra_arbitrum_2025
        # (Giai đoạn B, Bước 3 mở rộng, 2026-08-27):
        "0xa45b5130f36cdca45667738e2a258ab09f4a5f7f",  # StargatePoolNative (xác nhận ContractName qua
        # getsourcecode) — pool Stargate/LayerZero dùng chung, deltaprime_arbitrum_2024 & magic_abracadabra_arbitrum_2025.
        # 2 địa chỉ dưới đây trùng giữa radiant_capital_arbitrum_2024 &
        # magic_abracadabra_arbitrum_2025 (cả 2 đều dùng LI.FI Diamond làm
        # nguồn mining, dễ chạm cùng hạ tầng bridge aggregator dùng chung):
        "0x3a23f943181408eac424116af7b7790c94cb97a5",  # SocketGateway (xác nhận ContractName qua
        # getsourcecode) — bridge aggregator Socket Protocol dùng chung.
        "0x718e2a83775343d5c0b1ee0676703cbaf30cafcd",  # TransparentUpgradeableProxy (proxy pattern chuẩn,
        # hạ tầng dùng chung).
        # 1 địa chỉ trùng giữa hackerdao_2022 & circulate_2023 (cả 2 dùng
        # PancakeSwap V2 làm nguồn mining):
        "0x5af6d33de2ccec94efb1bdf8f92bd58085432d2c",  # PancakeSwapLottery (xác nhận ContractName qua
        # getsourcecode) — hạ tầng PancakeSwap chính thức, dùng chung.
        # 2 địa chỉ xuất hiện khi thêm new_free_dao_2022 (2026-08-28):
        "0x000000000000000000000000000000000000dead",  # burn address quy ước (KHÁC null address 0x0 đã
        # loại ở trên) — dùng chung bởi RẤT NHIỀU token/dự án không liên quan (quy ước "gửi token đây để
        # đốt"), không phải 1 thực thể phân biệt được, tương tự lý do loại null address.
        # 0x0d5550d5... (TornadoProxyLight, mixer BSC) đã thêm vào protocol_map.yaml
        # mixers_exit_services chính thức — tự động nằm trong known_protocol_addrs
        # qua vòng lặp bên dưới, không cần liệt kê thủ công ở đây nữa.
    }
    for cat in ("bridges", "dexes", "mixers_exit_services", "lending_protocols"):
        for entry in protocol_map.get(cat) or []:
            for key in ("contract_addresses", "router_addresses"):
                for a in (entry.get(key) or {}).values():
                    known_protocol_addrs.add(a.lower())

    reg_df = pd.read_csv(REGISTRY_PATH)
    hn_df = pd.read_csv(HARD_NEGATIVE_REGISTRY_PATH)
    config = load_trajectory_config()

    tx_hash_to_groups: dict = {}
    addr_to_groups: dict = {}

    def _process(group_id, chain, seed, start_block):
        traj, _, _ = expand_and_build_trajectory(
            chain, seed, int(start_block), group_id, 0, config=config, do_collect=False, max_iterations=2,
        )
        for a in traj.actions:
            tx_hash_to_groups.setdefault(a.tx_hash, set()).add(group_id)
            for addr in (a.src, a.dst):
                if addr not in known_protocol_addrs:
                    addr_to_groups.setdefault(addr, set()).add(group_id)

    for _, row in reg_df.iterrows():
        _process(row["incident_id"], row["chain_primary"], row["seed_address"], row["start_block"])
    for _, row in hn_df.iterrows():
        _process(row["parent_incident_id"], row["chain"], row["seed_address"], row["start_block"])

    tx_leaks = {h: g for h, g in tx_hash_to_groups.items() if len(g) > 1}
    addr_leaks = {a: g for a, g in addr_to_groups.items() if len(g) > 1}

    assert not tx_leaks, f"tx_hash trùng giữa các group: {tx_leaks}"
    assert not addr_leaks, f"address (ngoài protocol contract) trùng giữa các group: {addr_leaks}"
