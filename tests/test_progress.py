from __future__ import annotations

import eex_datasource.progress as progress_module


def test_progress_is_identity_without_tqdm(monkeypatch) -> None:
    monkeypatch.setattr(progress_module, "_tqdm", None)
    values = [1, 2, 3]
    assert progress_module.progress(values, desc="ignored") is values
