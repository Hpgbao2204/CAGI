"""
Canonical event schema — xem configs/features.yaml -> event_schema.

Mọi event trong pipeline CAGI-ED (từ collector/decoder cho tới trajectory
builder và feature extractor) phải đi qua CanonicalEvent trước khi được
lưu/ dùng tiếp, để đảm bảo tính nhất quán và chống lỗi schema drift.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

EventType = Literal[
    "transfer",
    "bridge_deposit",
    "bridge_withdraw",
    "lending_deposit",
    "lending_withdraw",
    "swap",
    "split",
    "merge",
    "mixer_or_exit",
    "other",
]


class CanonicalEvent(BaseModel):
    """Canonical on-chain event, chuẩn hóa theo configs/features.yaml.

    Required fields khớp đúng `event_schema.required_fields`. Optional
    fields khớp `event_schema.recommended_fields`.
    """

    model_config = ConfigDict(extra="forbid", frozen=False)

    # --- required fields ---
    chain_id: int = Field(..., description="EVM chain id, vd 1=eth, 56=bsc, 42161=arbitrum")
    block_number: int = Field(..., ge=0)
    timestamp: datetime = Field(..., description="Thời điểm block, phải là UTC-aware")
    tx_hash: str = Field(..., min_length=1)
    log_index: int = Field(..., ge=0)
    src: str = Field(..., min_length=1)
    dst: str = Field(..., min_length=1)
    event_type: EventType
    amount_norm: float = Field(
        ...,
        description=(
            "Giá trị đã chuẩn hóa (log-scaled hoặc ratio), KHÔNG phải raw amount "
            "(vd raw token amount ở base unit/wei)."
        ),
    )

    # --- recommended / optional fields ---
    protocol: Optional[str] = None
    token: Optional[str] = None
    counterparty_type: Optional[str] = None
    source_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("timestamp phải có timezone (UTC-aware), không được naive")
        if v.utcoffset() != timezone.utc.utcoffset(None):
            v = v.astimezone(timezone.utc)
        return v

    @field_validator("tx_hash")
    @classmethod
    def _tx_hash_format(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("0x") or len(v) != 66:
            raise ValueError("tx_hash phải là hex string dạng '0x' + 64 ký tự")
        return v.lower()

    @field_validator("src", "dst")
    @classmethod
    def _address_format(cls, v: str) -> str:
        v = v.strip()
        if not v.startswith("0x") or len(v) != 42:
            raise ValueError("address phải là hex string dạng '0x' + 40 ký tự")
        return v.lower()

    @field_validator("amount_norm")
    @classmethod
    def _amount_norm_not_raw(cls, v: float) -> float:
        # amount_norm phải là log-scaled hoặc ratio, không phải raw amount.
        # Heuristic cứng: raw token amounts ở base unit (wei/gwei-scale) thường
        # là số nguyên rất lớn (>= 1e6) hoặc số cực nhỏ dạng ratio hợp lệ nằm
        # trong khoảng hữu hạn. Ta chặn các giá trị "trông như raw wei amount"
        # để bắt lỗi phổ biến nhất: quên chuẩn hóa trước khi ghi.
        if v != v or v in (float("inf"), float("-inf")):
            raise ValueError("amount_norm phải là số hữu hạn")
        if abs(v) >= 1e6:
            raise ValueError(
                "amount_norm >= 1e6 trông giống raw amount chưa chuẩn hóa; "
                "hãy log-scale (vd log1p(raw_amount / 10**decimals)) hoặc dùng ratio"
            )
        return v

    def dedup_key(self) -> tuple:
        """Khóa chống trùng lặp event: (chain_id, tx_hash, log_index)."""
        return (self.chain_id, self.tx_hash, self.log_index)
