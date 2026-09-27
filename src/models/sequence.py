"""S1 baseline: a small GRU over typed action tokens (event type x log-scale
gap bucket, last 64 actions of the prefix), trained with a class-weighted
loss. Tests whether a sequence model learns the typed structure without
hand-crafted motifs.
"""
from __future__ import annotations

import math
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd

EVENT_TYPES = ["transfer", "bridge_deposit", "bridge_withdraw", "lending_deposit", "lending_withdraw",
               "swap", "split", "merge", "mixer_or_exit", "other"]
GAP_EDGES = [0, 10, 60, 600, 3600, 6 * 3600]  # giay
MAX_LEN = 64


def tokenize_prefix(actions) -> List[int]:
    toks = []
    for i, a in enumerate(actions):
        gap = 0.0 if i == 0 else (a.timestamp - actions[i - 1].timestamp).total_seconds()
        b = sum(gap >= e for e in GAP_EDGES[1:])
        toks.append(1 + EVENT_TYPES.index(a.event_type) * len(GAP_EDGES) + b)
    return toks[-MAX_LEN:]


class GRUSequenceModel:
    """fit/predict_proba giong cac model khac; X chi dung .index de tra
    chuoi token tu `seq_lookup` (index dong pooled -> list token)."""

    name = "S1_gru_typed_tokens"

    def __init__(self, seq_lookup: Dict[int, List[int]], epochs: int = 25, hidden: int = 32, emb: int = 16,
                 seed: int = 42) -> None:
        self.seq_lookup = seq_lookup
        self.epochs, self.hidden, self.emb, self.seed = epochs, hidden, emb, seed

    def _batch(self, idx):
        import torch
        seqs = [self.seq_lookup[i] or [0] for i in idx]
        L = max(len(s) for s in seqs)
        arr = np.zeros((len(seqs), L), dtype=np.int64)
        lens = np.array([len(s) for s in seqs])
        for r, s in enumerate(seqs):
            arr[r, : len(s)] = s
        return torch.from_numpy(arr), torch.from_numpy(lens)

    def _net(self):
        import torch
        import torch.nn as nn

        class Net(nn.Module):
            def __init__(s, n_tok, emb, hid):
                super().__init__()
                s.emb = nn.Embedding(n_tok, emb, padding_idx=0)
                s.gru = nn.GRU(emb, hid, batch_first=True)
                s.out = nn.Linear(hid, 1)

            def forward(s, x, lens):
                h = s.emb(x)
                packed = nn.utils.rnn.pack_padded_sequence(h, lens.clamp(min=1), batch_first=True, enforce_sorted=False)
                _, hn = s.gru(packed)
                return s.out(hn[-1]).squeeze(-1)

        return Net(1 + len(EVENT_TYPES) * len(GAP_EDGES), self.emb, self.hidden)

    def fit(self, X_train: pd.DataFrame, y_train: Sequence[int], groups_train=None) -> "GRUSequenceModel":
        import torch
        torch.manual_seed(self.seed)
        rng = np.random.default_rng(self.seed)
        idx = np.asarray(X_train.index)
        y = np.asarray(y_train, dtype=np.float32)
        self.net = self._net()
        pos_w = torch.tensor((len(y) - y.sum()) / max(y.sum(), 1.0))
        loss_fn = torch.nn.BCEWithLogitsLoss(pos_weight=pos_w)
        opt = torch.optim.Adam(self.net.parameters(), lr=3e-3)
        self.net.train()
        for _ in range(self.epochs):
            perm = rng.permutation(len(idx))
            for s in range(0, len(idx), 64):
                b = perm[s:s + 64]
                x, lens = self._batch(idx[b])
                opt.zero_grad()
                loss = loss_fn(self.net(x, lens), torch.from_numpy(y[b]))
                loss.backward()
                opt.step()
        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        import torch
        self.net.eval()
        idx = np.asarray(X.index)
        out = []
        with torch.no_grad():
            for s in range(0, len(idx), 256):
                x, lens = self._batch(idx[s:s + 256])
                out.append(torch.sigmoid(self.net(x, lens)).numpy())
        return np.concatenate(out) if out else np.array([])
