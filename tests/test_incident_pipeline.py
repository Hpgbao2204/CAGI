"""
Test cho pipeline tổng quát hóa (Bước A): src/pipeline/incident_pipeline.py.

Regression test bắt buộc: chạy pipeline với incident_id=ronin_bridge_2022 ở
chế độ do_collect=False (chỉ dùng cache data/raw/ đã có từ pilot, KHÔNG gọi
mạng) phải cho kết quả GIỐNG HỆT (về nội dung sự kiện, không nhất thiết
log_index/thứ tự) với kết quả pilot đã verify thủ công, lưu ở
tests/fixtures/golden/ronin_bridge_2022_events.golden.json.

So sánh theo tập hợp (tx_hash, event_type, src, dst, amount_norm làm tròn,
token) thay vì so JSON y hệt từng byte, vì log_index giả (internal tx) có
thể đổi giữa các lần chạy tùy thứ tự duyệt address — đây là artifact nội bộ,
không phải nội dung nghiệp vụ.
"""
import json
from pathlib import Path

import pytest

from src.pipeline.incident_pipeline import (
    compute_end_block,
    expand_and_build_trajectory,
    find_provenance_bridge_events,
    find_swap_evidence,
    load_incident_row,
    run_incident_pipeline,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
GOLDEN_DIR = REPO_ROOT / "tests" / "fixtures" / "golden"

# data/raw/ cache từ pilot Ronin không được commit lại mỗi lần (dữ liệu thật,
# phụ thuộc máy đã crawl) -> skip nếu cache không tồn tại trong môi trường
# hiện tại (vd CI chưa từng chạy collector thật).
RONIN_SEED_CACHE = REPO_ROOT / "data" / "raw" / "eth" / "0x098b716b8aaf21512996dc57eb0615e2383e2f96"

pytestmark = pytest.mark.skipif(
    not RONIN_SEED_CACHE.exists(),
    reason="Cần cache data/raw/ thật từ pilot Ronin Bridge (chưa crawl trong môi trường này)",
)


def _event_signature_set(events_json: list) -> set:
    return {
        (e["tx_hash"], e["event_type"], e["src"], e["dst"], round(e["amount_norm"], 6), e.get("token"))
        for e in events_json
    }


def test_load_incident_row_reads_seed_and_start_block():
    row = load_incident_row("ronin_bridge_2022")
    assert row["seed_address"] == "0x098b716b8aaf21512996dc57eb0615e2383e2f96"
    assert row["start_block"] == "14442775"
    assert row["chain_primary"] == "eth"
    assert row["label"] == "1"


def test_load_incident_row_unknown_id_raises():
    with pytest.raises(KeyError):
        load_incident_row("does_not_exist_incident")


def test_regression_ronin_bridge_2022_matches_pilot_golden():
    golden = json.loads((GOLDEN_DIR / "ronin_bridge_2022_events.golden.json").read_text(encoding="utf-8"))
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "ronin_bridge_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }

    assert new_sig == golden_sig, (
        f"Pipeline tổng quát hóa cho kết quả KHÁC pilot đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    # Frontier expansion tự động phải tìm ra đúng 2 hop address đã biết
    # trong pilot (0x665660f6..., 0xe708f172...), không cần hardcode.
    assert "0x665660f65e94454a64b96693a67a41d440155617" in processed
    assert "0xe708f17240732bbfa1baa8513f66b665fbc7ce10" in processed
    assert len(provenance_events) == 2  # 173,600 ETH + 25.5M USDC


def test_regression_ronin_benign_control_matches_golden():
    """Golden fixture cập nhật 2026-08-14 (rà soát cache/pagination hệ
    thống, xem annotation_guide.md mục 14): sau khi sửa bug dedup +
    wipe-before-write, phát hiện thêm 2 provenance event thật (đều từ Ronin
    Bridge đã verify, cùng seed) trước đây bị bỏ sót — 3 tổng (2 USDC + 1
    ETH), không phải 1."""
    golden = json.loads(
        (GOLDEN_DIR / "ronin_benign_control_2022_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "ronin_benign_control_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig
    assert len(provenance_events) == 3


QBRIDGE_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0xd01ae1a708614948b2b5e0b7ab5be6afa01325c7"
BSC_TOKEN_HUB_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0x489a8756c18c0b8b24ec2a2b9ff3d4d447f79bec"


@pytest.mark.skipif(
    not QBRIDGE_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho qbridge_qubit_2022 (chưa crawl trong môi trường này)",
)
def test_regression_qbridge_qubit_2022_matches_golden():
    """Golden fixture thêm 2026-08-13 (Bước 3, sau khi verify xong 3 bug
    merge_events_into_semantic_actions/decode_tokentx_row/decode_bsctrace_transfer_row)
    — khóa cứng 22 action, xác nhận KHÔNG đổi qua các lần sửa decoder trước
    đó (xem metadata/annotation_guide.md mục 9-10). Test này PHẢI fail ngay
    nếu 1 lần sửa decoder sau này vô tình đổi lại nội dung mà không review."""
    golden = json.loads(
        (GOLDEN_DIR / "qbridge_qubit_2022_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "qbridge_qubit_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )


@pytest.mark.skipif(
    not BSC_TOKEN_HUB_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho bsc_token_hub_2022 (chưa crawl trong môi trường này)",
)
def test_regression_bsc_token_hub_2022_matches_golden():
    """Golden fixture thêm 2026-08-13 (Bước 3) — khóa cứng 66 action (bao
    gồm 3 action lending_deposit tới Venus Protocol, tổng ~900,000 BNB,
    khớp báo cáo Elliptic công khai — xem metadata/annotation_guide.md mục
    11). Test này PHẢI fail ngay nếu 1 lần sửa decoder/protocol_map.yaml sau
    này vô tình đổi lại nội dung mà không review, đặc biệt là mất lại
    lending_deposit như đã từng xảy ra qua 4 bug liên tiếp phát hiện hôm
    nay."""
    golden = json.loads(
        (GOLDEN_DIR / "bsc_token_hub_2022_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "bsc_token_hub_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    lending_actions = [a for a in traj.actions if a.event_type == "lending_deposit"]
    assert len(lending_actions) == 3, "phải giữ đúng 3 action lending_deposit (Venus Protocol)"


CHIBI_SEED_CACHE = REPO_ROOT / "data" / "raw" / "arbitrum" / "0x80c1ca8f002744a3b22ac5ba6ffc4dc0deda58e3"
WOOPPV2_SEED_CACHE = REPO_ROOT / "data" / "raw" / "arbitrum" / "0x9961190b258897bca7a12b8f37f415e689d281c4"
UTOPIASPHERE_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0x6e12ce089a8bedea49532010229f0913475d8d9c"


@pytest.mark.skipif(
    not CHIBI_SEED_CACHE.exists(),
    reason="Cần cache data/raw/arbitrum/ thật cho chibi_finance_2023 (chưa crawl trong môi trường này)",
)
def test_regression_chibi_finance_2023_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 4, mở rộng dataset lên 8
    incident) — khóa cứng 6 action (2 bridge_deposit Multichain+Stargate
    tổng ~556.4 ETH khớp báo cáo CertiK, 1 swap, 3 leg USDC.e). Xem
    metadata/annotation_guide.md mục 12."""
    golden = json.loads(
        (GOLDEN_DIR / "chibi_finance_2023_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "chibi_finance_2023", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 2, "phải giữ đúng 2 action bridge_deposit (Multichain + Stargate)"


@pytest.mark.skipif(
    not WOOPPV2_SEED_CACHE.exists(),
    reason="Cần cache data/raw/arbitrum/ thật cho wooppv2_2024 (chưa crawl trong môi trường này)",
)
def test_regression_wooppv2_2024_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 4) — khóa cứng 6 action (2
    bridge_deposit Stargate tổng ~200.1 ETH, 4 swap WOO). Xem
    metadata/annotation_guide.md mục 12."""
    golden = json.loads(
        (GOLDEN_DIR / "wooppv2_2024_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "wooppv2_2024", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 2, "phải giữ đúng 2 action bridge_deposit (Stargate)"


@pytest.mark.skipif(
    not UTOPIASPHERE_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho utopiasphere_2024 (chưa crawl trong môi trường này)",
)
def test_regression_utopiasphere_2024_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 4) — khóa cứng 13 action (11
    bridge_deposit LI.FI Diamond tổng ~1071.5 BNB, 1 swap UPS). Xem
    metadata/annotation_guide.md mục 12.

    Cập nhật 2026-08-27 (fix bug value_share gộp-token, xem
    src/trajectories/builder.py::outflow_by_src_token và
    results/reports/value_share_unit_mix_fix_v1.md): trajectory mở rộng
    nhiều hơn thật sự (evidence bridge_deposit trước đây bị loại oan do mẫu
    số tainted-share gộp nhiều token khác nhau) — 11 -> 20 bridge_deposit."""
    golden = json.loads(
        (GOLDEN_DIR / "utopiasphere_2024_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "utopiasphere_2024", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 20, "phải giữ đúng 20 action bridge_deposit (LI.FI Diamond, sau fix value_share)"


XKINGDOM_SEED_CACHE = REPO_ROOT / "data" / "raw" / "arbitrum" / "0xef7dd2264f41107ba90ec7d3b88444f987d6a13d"
WAULT_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0x886358f9296de461d12e791bc9ef6f5a03410c64"
PARALUNI_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0x94bc1d555e63eea23fe7fdbf937ef3f9ac5fcf8f"
CIRCULATE_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0x5695ef5f2e997b2e142b38837132a6c3ddc463b7"


@pytest.mark.skipif(
    not XKINGDOM_SEED_CACHE.exists(),
    reason="Cần cache data/raw/arbitrum/ thật cho xkingdom_2024 (chưa crawl trong môi trường này)",
)
def test_regression_xkingdom_2024_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 4, mở rộng dataset lên 12
    incident) — khóa cứng 9 action (1 bridge_deposit Stargate ~100 ETH,
    evidence thay thế mixer trên chain khác — xem
    metadata/annotation_guide.md mục 13).

    Cập nhật 2026-08-27 (fix bug value_share gộp-token — xem
    results/reports/value_share_unit_mix_fix_v1.md): thêm nhiều
    bridge_deposit thật (Across Protocol SpokePool) trước đây bị loại oan
    — 1 -> 20 bridge_deposit."""
    golden = json.loads(
        (GOLDEN_DIR / "xkingdom_2024_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "xkingdom_2024", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 20, "phải giữ đúng 20 action bridge_deposit (Stargate/Across, sau fix value_share)"


@pytest.mark.skipif(
    not WAULT_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho wault_finance_2021 (chưa crawl trong môi trường này)",
)
def test_regression_wault_finance_2021_matches_golden():
    """Golden fixture cập nhật 2026-08-14 (rà soát cache/pagination hệ
    thống, xem annotation_guide.md mục 14) — sau khi sửa bug dedup +
    wipe-before-write + allowlist, trajectory mở rộng đúng hơn xuống các hop
    tiếp theo (0x146cd24d -> nhiều địa chỉ khác), tổng 15 action thay vì 6
    trước đây. 3 swap ETH->anyETH gốc (tổng ~370.65 ETH, khớp chính xác báo
    cáo SlowMist) VẪN CÒN NGUYÊN — kiểm tra như tập con thay vì khoá cứng
    tổng số swap (vì nay có thêm swap ở các hop xa hơn seed)."""
    golden = json.loads(
        (GOLDEN_DIR / "wault_finance_2021_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "wault_finance_2021", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    core_swap_txs = {"0xf04f4dfad1", "0xc92a1a1e9d", "0xc4aa1c1248"}  # ETH->anyETH gốc, khớp SlowMist
    swap_actions = [a for a in traj.actions if a.event_type == "swap"]
    core_present = {a.tx_hash[:12] for a in swap_actions} & core_swap_txs
    assert core_present == core_swap_txs, "3 swap ETH->anyETH gốc (khớp SlowMist) phải còn nguyên"
    assert len(swap_actions) >= 3, "phải có ít nhất 3 action swap gốc"


@pytest.mark.skipif(
    not PARALUNI_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho paraluni_2022 (chưa crawl trong môi trường này)",
)
def test_regression_paraluni_2022_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 4) — khóa cứng 16 action (3
    swap PancakeSwap V2 tổng ~1187 BNB). Xem metadata/annotation_guide.md
    mục 13.

    Cập nhật 2026-08-27 (fix bug value_share gộp-token — xem
    results/reports/value_share_unit_mix_fix_v1.md, và điều tra lại
    results/reports/paraluni_2022_reinvestigation.md): trajectory mở rộng
    RẤT NHIỀU (38 -> 511 action ở max_depth=6 chính thức) — 3 -> 76 swap
    PancakeSwap V2/V3 thật."""
    golden = json.loads(
        (GOLDEN_DIR / "paraluni_2022_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "paraluni_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    swap_actions = [a for a in traj.actions if a.event_type == "swap"]
    assert len(swap_actions) == 76, "phải giữ đúng 76 action swap (PancakeSwap V2/V3, sau fix value_share)"


@pytest.mark.skipif(
    not CIRCULATE_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho circulate_2023 (chưa crawl trong môi trường này)",
)
def test_regression_circulate_2023_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 4) — khóa cứng 5 action (toàn
    bộ 'transfer', KHÔNG có swap/bridge_deposit chính thức — gate đạt qua
    evidence thay thế, xem metadata/annotation_guide.md mục 13)."""
    golden = json.loads(
        (GOLDEN_DIR / "circulate_2023_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "circulate_2023", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )


FEG_BRIDGE_SEED_CACHE = REPO_ROOT / "data" / "raw" / "eth" / "0xcb96dde53f43035f7395d8dbdb652987f7630b3c"
DELTAPRIME_SEED_CACHE = REPO_ROOT / "data" / "raw" / "arbitrum" / "0x56e7f67211683857ee31a1220827cac5cdaa634c"


@pytest.mark.skipif(
    not FEG_BRIDGE_SEED_CACHE.exists(),
    reason="Cần cache data/raw/eth/ thật cho feg_bridge_2024 (chưa crawl trong môi trường này)",
)
def test_regression_feg_bridge_2024_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 0, Tuần 5) — khóa cứng 9 action
    (toàn bộ 'mixer_or_exit' vào Tornado Cash Router, tổng ~18.27 ETH log-scale)
    — evidence thay thế (không có bridge_deposit/swap chính thức, xem
    metadata/annotation_guide.md mục 5). Đã xác nhận KHÔNG đổi qua so sánh
    thủ công ở v0.8 (rà soát cache/pagination hệ thống) — đây là lần đầu
    khoá cứng bằng golden fixture."""
    golden = json.loads(
        (GOLDEN_DIR / "feg_bridge_2024_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "feg_bridge_2024", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    mixer_actions = [a for a in traj.actions if a.event_type == "mixer_or_exit"]
    assert len(mixer_actions) == 9, "phải giữ đúng 9 action mixer_or_exit (Tornado Cash Router)"


@pytest.mark.skipif(
    not DELTAPRIME_SEED_CACHE.exists(),
    reason="Cần cache data/raw/arbitrum/ thật cho deltaprime_arbitrum_2024 (chưa crawl trong môi trường này)",
)
def test_regression_deltaprime_arbitrum_2024_matches_golden():
    """Golden fixture thêm 2026-08-14 (Bước 0, Tuần 5) — khóa cứng 5 action
    (1 bridge_deposit Across Protocol SpokePool ~1.378 WBTC log-scale, 4
    transfer). Đã xác nhận KHÔNG đổi qua so sánh thủ công ở v0.8 — đây là
    lần đầu khoá cứng bằng golden fixture."""
    golden = json.loads(
        (GOLDEN_DIR / "deltaprime_arbitrum_2024_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "deltaprime_arbitrum_2024", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 1, "phải giữ đúng 1 action bridge_deposit (Across Protocol)"


RADIANT_SEED_CACHE = REPO_ROOT / "data" / "raw" / "arbitrum" / "0x0629b1048298ae9deff0f4100a31967fb3f98962"


@pytest.mark.skipif(
    not RADIANT_SEED_CACHE.exists(),
    reason="Cần cache data/raw/arbitrum/ thật cho radiant_capital_arbitrum_2024 (chưa crawl trong môi trường này)",
)
def test_regression_radiant_capital_arbitrum_2024_matches_golden():
    """Golden fixture thêm 2026-08-27 (Giai đoạn B, Bước 3 — incident thứ 12
    của dataset). Radiant Capital exploit (Oct 16 2024, multisig compromise
    qua malware, Mandiant quy cho UNC4736/Bắc Triều Tiên) — xác minh qua 5
    nguồn độc lập (Halborn, CoinDesk, ChainCatcher, rekt.news, post-mortem
    chính thức của Radiant). seed_address = 0x0629b1048298... (địa chỉ
    attacker rekt.news gọi là "BSC Attacker" nhưng CŨNG hoạt động thật trên
    Arbitrum — đã xác nhận qua chuỗi dòng tiền on-chain thật khớp báo cáo:
    0x0629b1048298 -> 0x97a05becc2 (~11,977 ETH, block 264523635) ->
    0x8b75e47976 (~12,127.7 ETH, block 264566947, địa chỉ "Arbitrum
    Attacker"/điểm gom quỹ cuối theo rekt.news)).

    Trajectory chỉ hoạt động ĐÚNG sau khi sửa bug value_share gộp-token
    (2026-08-27, xem src/trajectories/builder.py::outflow_by_src_token) —
    trước đó bị EMPTY vì giao dịch ETH thật (11,977 ETH) bị tính
    value_share sai (0.24%) do mẫu số cộng dồn lẫn nhiều swap ARB/WBTC/USDC
    nhỏ khác. Khóa cứng 248 action (56 bridge_deposit LI.FI Diamond, 185
    transfer, 4 merge, 3 swap)."""
    golden = json.loads(
        (GOLDEN_DIR / "radiant_capital_arbitrum_2024_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "radiant_capital_arbitrum_2024", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 56, "phải giữ đúng 56 action bridge_deposit (LI.FI Diamond)"

    # Xac nhan dung chuoi dong tien khop bao cao cong khai: seed -> trung
    # gian (0x97a05becc2) -> diem gom quy cuoi (0x8b75e47976), ca 2 chan deu
    # la native ETH transfer voi gia tri lon (log-scale > 9.0, tuong duong
    # hang nghin ETH raw).
    intermediary = "0x97a05becc2e7891d07f382457cd5d57fd242e4e8"
    final_dest = "0x8b75e47976c3c500d0148463931717001f620887"
    hop1 = [a for a in traj.actions if a.src == "0x0629b1048298ae9deff0f4100a31967fb3f98962" and a.dst == intermediary]
    hop2 = [a for a in traj.actions if a.src == intermediary and a.dst == final_dest]
    assert len(hop1) >= 1 and hop1[0].amount_norm > 9.0, "phải có chuyển ETH lớn seed -> trung gian"
    assert len(hop2) >= 1 and hop2[0].amount_norm > 9.0, "phải có chuyển ETH lớn trung gian -> điểm gom quỹ cuối"


MAGIC_SEED_CACHE = REPO_ROOT / "data" / "raw" / "arbitrum" / "0x51c9d0264d829a4f6d525df2357cd20ea79b5049"


@pytest.mark.skipif(
    not MAGIC_SEED_CACHE.exists(),
    reason="Cần cache data/raw/arbitrum/ thật cho magic_abracadabra_arbitrum_2025 (chưa crawl trong môi trường này)",
)
def test_regression_magic_abracadabra_arbitrum_2025_matches_golden():
    """Golden fixture thêm 2026-08-27 (Giai đoạn B, Bước 3 mở rộng — incident
    thứ 13). Abracadabra Money (MIM) GMX V2 Cauldron exploit (25/3/2025,
    ~$13M, CertiK + threesigma.xyz phân tích) — seed_address
    0x51c9d0264d829a4f6d525df2357cd20ea79b5049 xác nhận qua on-chain thật:
    nhận 0.1 ETH funding tại block 319305624 (2025-03-25 09:11:46 UTC, khớp
    "funded morning of attack" theo threesigma.xyz), sau đó nhiều lần gọi
    `cook()` (hàm đặc trưng GmxV2CauldronV4.cook() theo báo cáo). Khóa cứng
    88 action (2 bridge_deposit LI.FI Diamond, 69 transfer, 13 split, 3 swap,
    1 merge) — route bridge thật là LI.FI Diamond (aggregator, có thể route
    qua Stargate ngầm như báo cáo mô tả, không mâu thuẫn)."""
    golden = json.loads(
        (GOLDEN_DIR / "magic_abracadabra_arbitrum_2025_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "magic_abracadabra_arbitrum_2025", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    bridge_actions = [a for a in traj.actions if a.event_type == "bridge_deposit"]
    assert len(bridge_actions) == 2, "phải giữ đúng 2 action bridge_deposit (LI.FI Diamond)"


HACKERDAO_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0xcfc591db031b760961fe8943a183741ed7cd1f82"


@pytest.mark.skipif(
    not HACKERDAO_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho hackerdao_2022 (chưa crawl trong môi trường này)",
)
def test_regression_hackerdao_2022_matches_golden():
    """Golden fixture thêm 2026-08-27 (Giai đoạn B, Bước 3 mở rộng — incident
    thứ 14). Hackerdao token flash loan exploit (24/5/2022, ~200 BNB/~$65K,
    CertiK) — seed_address 0xcfc591db031b760961fe8943a183741ed7cd1f82 xác
    nhận qua on-chain thật: hoạt động tại block 17361150-17361615 khớp chính
    xác BlockNumber AMLGuard (17361150). CertiK báo cáo tiền chuyển vào
    Tornado Cash sau đó — ban đầu KHÔNG bắt được (BSC's Tornado Cash biến
    thể `TornadoProxyLight` chưa có trong protocol_map.yaml), chỉ có evidence
    thay thế (2 swap PancakeSwap V2). Cập nhật 2026-08-28: phát hiện
    `TornadoProxyLight` khi điều tra leakage với `new_free_dao_2022` — thêm
    vào `protocol_map.yaml` mixers_exit_services — nay bắt được ĐÚNG 4 action
    `mixer_or_exit` khớp báo cáo CertiK. Khóa cứng 35 action (29 transfer, 4
    mixer_or_exit, 2 swap)."""
    golden = json.loads(
        (GOLDEN_DIR / "hackerdao_2022_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "hackerdao_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    swap_actions = [a for a in traj.actions if a.event_type == "swap"]
    assert len(swap_actions) == 2, "phải giữ đúng 2 action swap (PancakeSwap V2)"


NEW_FREE_DAO_SEED_CACHE = REPO_ROOT / "data" / "raw" / "bsc" / "0x22c9736d4fc73a8fa0eb436d2ce919f5849d6fd2"


@pytest.mark.skipif(
    not NEW_FREE_DAO_SEED_CACHE.exists(),
    reason="Cần cache data/raw/bsc/ thật cho new_free_dao_2022 (chưa crawl trong môi trường này)",
)
def test_regression_new_free_dao_2022_matches_golden():
    """Golden fixture thêm 2026-08-27 (Giai đoạn B, Bước 3 mở rộng). New Free
    DAO (NFD) flash loan exploit (8/9/2022, ~4481 WBNB/~$1.25M, 6+ nguồn độc
    lập: Halborn, ImmuneBytes, QuillAudits, Cointelegraph, BeInCrypto,
    CryptoSlate) — seed_address 0x22c9736d... xác nhận qua on-chain thật:
    funding tại block 17689293 khớp chính xác BlockNumber AMLGuard.

    Cập nhật 2026-08-28: phát hiện `TornadoProxyLight` (mixer Tornado Cash
    trên BSC, xem `metadata/protocol_map.yaml`) khi điều tra leakage với
    `hackerdao_2022` — trước đó KHÔNG có trong protocol_map nên 9/12 giao
    dịch tới đây bị tính value_share dưới ngưỡng, chỉ giữ transfer thường.
    Sau khi thêm vào mixer_allowlist: 12 action, TOÀN BỘ là `mixer_or_exit`
    — khớp CHÍNH XÁC báo cáo công khai ("$111,544 vào Tornado Cash"). Nâng
    `eval_tier` từ `auxiliary_low_evidence` lên `primary`."""
    golden = json.loads(
        (GOLDEN_DIR / "new_free_dao_2022_events.golden.json").read_text(encoding="utf-8")
    )
    golden_sig = _event_signature_set(golden)

    traj, provenance_events, processed = run_incident_pipeline(
        "new_free_dao_2022", do_collect=False, write_output=False
    )
    new_sig = {
        (a.tx_hash, a.event_type, a.src, a.dst, round(a.amount_norm, 6), a.token) for a in traj.actions
    }
    assert new_sig == golden_sig, (
        f"Pipeline cho kết quả KHÁC golden đã verify.\n"
        f"Chỉ có ở golden: {golden_sig - new_sig}\n"
        f"Chỉ có ở kết quả mới: {new_sig - golden_sig}"
    )
    mixer_actions = [a for a in traj.actions if a.event_type == "mixer_or_exit"]
    assert len(mixer_actions) == 12, "phải giữ đúng 12 action mixer_or_exit (TornadoProxyLight)"


def test_run_incident_pipeline_does_not_write_when_write_output_false(tmp_path, monkeypatch):
    import src.pipeline.incident_pipeline as mod

    monkeypatch.setattr(mod, "PROCESSED_DIR", tmp_path)
    run_incident_pipeline("ronin_bridge_2022", do_collect=False, write_output=False)
    assert not any(tmp_path.glob("*.json"))


def test_run_incident_pipeline_writes_output_file(tmp_path, monkeypatch):
    import src.pipeline.incident_pipeline as mod

    monkeypatch.setattr(mod, "PROCESSED_DIR", tmp_path)
    run_incident_pipeline("ronin_bridge_2022", do_collect=False, write_output=True)
    out_files = list(tmp_path.glob("ronin_bridge_2022_events.json"))
    assert len(out_files) == 1


def test_load_events_for_addresses_dispatches_to_bsctrace_for_bsc(tmp_path, monkeypatch):
    """chain='bsc' phải đọc cache theo format BSCTrace (response.result.transfers),
    KHÔNG phải format Etherscan (response.result là list) — xác nhận dispatch
    đúng nhánh trong load_events_for_addresses.
    """
    import src.pipeline.incident_pipeline as mod

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    addr = "0x" + "1" * 40
    incident_id = "test_incident"
    cache_dir = tmp_path / "bsc" / addr / incident_id
    cache_dir.mkdir(parents=True)
    record = {
        "requested_at_utc": "2026-08-13T00:00:00+00:00",
        "checksum_sha256": "dummy",
        "response": {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "transfers": [
                    {
                        "blockNum": "0x100",
                        "hash": "0x" + "a" * 64,
                        "from": addr,
                        "to": "0x" + "2" * 40,
                        "value": "0x29a2241af62c0000",  # 3.0 * 10**18 wei (hex raw base-unit)
                        "asset": "BNB",
                        "category": "external",
                        "blockTimeStamp": 1643320487,
                        "logIndex": 0,
                    }
                ],
                "pageToken": "",
            },
        },
    }
    (cache_dir / "assettransfers_w0.json").write_text(json.dumps(record), encoding="utf-8")

    events = mod.load_events_for_addresses("bsc", [addr], incident_id, bridge_index={}, mixer_index={})
    assert len(events) == 1
    assert events[0].event_type == "transfer"
    assert events[0].token == "BNB"


def test_expand_and_build_trajectory_filters_events_before_start_block(tmp_path, monkeypatch):
    """Regression test: BSCTrace (không lọc block-range server-side) trả về
    TOÀN BỘ lịch sử của address — nếu không lọc block_number < start_block
    trước khi build_trajectory, build_trajectory lấy start_time từ event
    CŨ NHẤT trong toàn bộ lịch sử (có thể cách incident nhiều năm), làm
    time_horizon_hours loại hết event thật liên quan tới incident. Bug thật
    phát hiện khi chạy QBridge (2026-08-13): 671 event decode được nhưng
    trajectory rỗng.
    """
    import src.pipeline.incident_pipeline as mod
    from src.trajectories.builder import TrajectoryConfig

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    seed = "0x" + "1" * 40
    cache_dir = tmp_path / "bsc" / seed / "test_incident"
    cache_dir.mkdir(parents=True)

    old_row = {
        "blockNum": "0x1",  # rất cũ, cách xa start_block
        "hash": "0x" + "a" * 64,
        "from": seed,
        "to": "0x" + "2" * 40,
        "value": "0xde0b6b3a7640000",
        "asset": "BNB",
        "category": "external",
        "blockTimeStamp": 1000000000,  # 2001 - rất xa incident
        "logIndex": 0,
    }
    recent_row = {
        "blockNum": "0x100",  # >= start_block giả định
        "hash": "0x" + "b" * 64,
        "from": seed,
        "to": "0x" + "3" * 40,
        "value": "0xde0b6b3a7640000",
        "asset": "BNB",
        "category": "external",
        "blockTimeStamp": 1643320487,  # gần incident thật
        "logIndex": 0,
    }
    record = {
        "requested_at_utc": "2026-08-13T00:00:00+00:00",
        "checksum_sha256": "dummy",
        "response": {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [old_row, recent_row], "pageKey": ""}},
    }
    (cache_dir / "assettransfers_w0.json").write_text(json.dumps(record), encoding="utf-8")

    config = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)
    traj, _, _ = expand_and_build_trajectory(
        "bsc", seed, start_block=256, incident_id="test_incident", label=1,
        config=config, do_collect=False, max_iterations=1,
    )
    tx_hashes = {a.tx_hash for a in traj.actions}
    assert "0x" + "b" * 64 in tx_hashes  # event gần incident PHẢI có mặt
    assert "0x" + "a" * 64 not in tx_hashes  # event cũ PHẢI bị lọc


def test_expand_and_build_trajectory_dilution_bug_many_events_after_end_block(tmp_path, monkeypatch):
    """Regression test: bug thật khi chạy QBridge (2026-08-13) — nếu chỉ lọc
    block_number >= start_block mà KHÔNG lọc <= end_block, hàng trăm giao
    dịch KHÔNG liên quan (nhiều tuần sau incident) pha loãng mẫu số
    outflow_by_src trong build_trajectory, khiến value_share của giao dịch
    thật không bao giờ đạt min_tainted_share -> trajectory rỗng dù có event
    thật. Test: 1 giao dịch thật lớn trong window + 50 giao dịch nhỏ NGOÀI
    window (nhiều tuần sau) -> giao dịch thật PHẢI được giữ.
    """
    import src.pipeline.incident_pipeline as mod
    from src.trajectories.builder import TrajectoryConfig

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    seed = "0x" + "1" * 40
    cache_dir = tmp_path / "bsc" / seed / "test_incident2"
    cache_dir.mkdir(parents=True)

    def _row(tx_hash, block_num, ts, value_hex="0xde0b6b3a7640000", log_index=0):
        return {
            "blockNum": hex(block_num),
            "hash": tx_hash,
            "from": seed,
            "to": "0x" + "2" * 40,
            "value": value_hex,
            "asset": "BNB",
            "category": "external",
            "blockTimeStamp": ts,
            "logIndex": log_index,
        }

    start_block = 1000
    real_row = _row("0x" + "b" * 64, start_block + 10, 1_600_000_000)
    # 50 giao dịch nhỏ, rất xa sau start_block (ngoài time_horizon 72h) ->
    # PHẢI bị lọc theo end_block, không được góp vào mẫu số tainted-share.
    dilution_rows = [
        _row(f"0x{i:064x}", start_block + 10_000_000 + i, 1_600_000_000 + 999_999 * i, log_index=i)
        for i in range(50)
    ]
    record = {
        "requested_at_utc": "2026-08-13T00:00:00+00:00",
        "checksum_sha256": "dummy",
        "response": {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [real_row] + dilution_rows, "pageKey": ""}},
    }
    (cache_dir / "assettransfers_w0.json").write_text(json.dumps(record), encoding="utf-8")

    config = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)
    traj, _, _ = expand_and_build_trajectory(
        "bsc", seed, start_block=start_block, incident_id="test_incident2", label=1,
        config=config, do_collect=False, max_iterations=1,
    )
    tx_hashes = {a.tx_hash for a in traj.actions}
    assert "0x" + "b" * 64 in tx_hashes, "Giao dịch thật bị loại do mẫu số bị pha loãng bởi event ngoài window"


def test_compute_end_block_uses_approx_blocks_per_hour():
    from src.trajectories.builder import TrajectoryConfig

    config = TrajectoryConfig(max_depth=6, time_horizon_hours=72, min_tainted_share=0.05)
    end_block = compute_end_block("eth", start_block=1000, config=config)
    assert end_block == 1000 + int(72 * 280)


def test_find_swap_evidence_includes_inbound_swap_outside_trajectory(tmp_path, monkeypatch):
    """Swap "chảy vào" seed (src != seed) không được builder chấp nhận vào
    trajectory (forward-only), nhưng PHẢI xuất hiện trong find_swap_evidence
    làm bằng chứng DEX bổ sung — đúng pattern áp dụng cho QBridge 2026-08-13.
    """
    import src.pipeline.incident_pipeline as mod

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    seed = "0x" + "1" * 40
    pool = "0x" + "9" * 40  # LP pool, không nằm trong node_depth (chỉ là src của swap trả về)
    incident_id = "test_incident"
    cache_dir = tmp_path / "bsc" / seed / incident_id
    cache_dir.mkdir(parents=True)

    # 2 event cùng tx_hash, khác token -> merge_events_into_semantic_actions
    # phân loại 'swap'; src=pool (không phải seed) nên bị builder loại khỏi
    # outbound trajectory, nhưng vẫn phải xuất hiện trong swap evidence.
    leg_out = {
        "blockNum": "0x100", "hash": "0x" + "e" * 64, "from": seed, "to": pool,
        "value": "0xde0b6b3a7640000", "asset": "BUSD", "category": "20", "decimal": "18",
        "blockTimeStamp": 1643320487, "logIndex": 0,
    }
    leg_in = {
        "blockNum": "0x100", "hash": "0x" + "e" * 64, "from": pool, "to": seed,
        "value": "0x16345785d8a0000", "asset": "BNB", "category": "internal",
        "blockTimeStamp": 1643320487, "logIndex": 1,
    }
    record = {
        "requested_at_utc": "2026-08-13T00:00:00+00:00",
        "checksum_sha256": "dummy",
        "response": {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [leg_out, leg_in], "pageKey": ""}},
    }
    (cache_dir / "assettransfers_w0.json").write_text(json.dumps(record), encoding="utf-8")

    evidence = find_swap_evidence("bsc", [seed], incident_id, start_block=1, end_block=1000, bridge_index={}, mixer_index={})
    assert len(evidence) == 1
    assert evidence[0].event_type == "swap"
    assert evidence[0].tx_hash == "0x" + "e" * 64


def test_find_provenance_bridge_events_detects_native_bnb_on_bsc(tmp_path, monkeypatch):
    """Regression test (bug thật BSC Token Hub 2026-08-13): provenance bridge
    event bằng native BNB (category=external/internal) PHẢI được phát hiện,
    không chỉ ERC-20 (category="20") — decode_bsctrace_transfer_row chỉ tự
    gắn nhãn bridge_withdraw cho category="20", nên find_provenance_bridge_events
    phải tự kiểm tra from/to thủ công cho native BNB.
    """
    import src.pipeline.incident_pipeline as mod

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    seed = "0x" + "1" * 40
    incident_id = "test_incident"
    bridge_contract = "0x0000000000000000000000000000000000001004"
    cache_dir = tmp_path / "bsc" / seed / incident_id
    cache_dir.mkdir(parents=True)

    native_bridge_row = {
        "blockNum": "0x100", "hash": "0x" + "d" * 64, "from": bridge_contract, "to": seed,
        "value": "0xd3c21bcecceda1000000",  # 1,000,000 BNB
        "asset": "BNB", "category": "internal", "blockTimeStamp": 1665080806, "logIndex": 0,
    }
    record = {
        "requested_at_utc": "2026-08-13T00:00:00+00:00",
        "checksum_sha256": "dummy",
        "response": {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [native_bridge_row], "pageKey": ""}},
    }
    (cache_dir / "assettransfers_w0.json").write_text(json.dumps(record), encoding="utf-8")

    bridge_index = {bridge_contract: {"name": "BSC Token Hub", "verify_status": "verified"}}
    events = find_provenance_bridge_events("bsc", seed, incident_id, bridge_index)
    assert len(events) == 1
    assert events[0].event_type == "bridge_withdraw"
    assert events[0].protocol == "BSC Token Hub"


def test_load_cached_bsctrace_rows_dedups_across_overlapping_page_files(tmp_path, monkeypatch):
    """Regression test (bug thật BSC Token Hub 2026-08-13): cùng 1 transfer
    (hash+category+logIndex giống nhau) xuất hiện ở 2 file cache khác nhau
    (vd fetch lại nhiều lần) KHÔNG được đếm 2 lần.
    """
    import src.pipeline.incident_pipeline as mod

    monkeypatch.setattr(mod, "RAW_DIR", tmp_path)
    addr = "0x" + "1" * 40
    incident_id = "test_incident"
    cache_dir = tmp_path / "bsc" / addr / incident_id
    cache_dir.mkdir(parents=True)

    row = {
        "blockNum": "0x100", "hash": "0x" + "a" * 64, "from": "0x" + "2" * 40, "to": addr,
        "value": "0xde0b6b3a7640000", "asset": "BNB", "category": "internal",
        "blockTimeStamp": 1643320487, "logIndex": 0,
    }
    for i in range(2):  # 2 file cache khác nhau, CÙNG 1 transfer (mô phỏng fetch trùng)
        record = {
            "requested_at_utc": "2026-08-13T00:00:00+00:00", "checksum_sha256": "dummy",
            "response": {"jsonrpc": "2.0", "id": 1, "result": {"transfers": [row], "pageKey": ""}},
        }
        (cache_dir / f"assettransfers_w{i}.json").write_text(json.dumps(record), encoding="utf-8")

    rows = mod._load_cached_bsctrace_rows(addr, incident_id)
    assert len(rows) == 1
