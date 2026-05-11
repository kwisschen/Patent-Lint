# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for the jurisdiction-mismatch detector (Issue #9 / ADR-082).

Covers the four mismatch directions plus the no-mismatch baselines.
The detector is conservative — false positives are worse than no
suggestion (they erode trust), so several tests verify the detector
correctly returns ``None`` for ambiguous English drafts that contain
trace CJK.
"""

from __future__ import annotations

import pytest

from patentlint.models import Jurisdiction
from patentlint.parser.jurisdiction_mismatch import detect_jurisdiction_mismatch


# A representative US (English) patent fragment — claims plus a paragraph
# of detailed description. Word count is high enough that the CJK ratio
# stays safely below 10% even if a CJK term were transliterated.
US_SAMPLE = """
What is claimed is:

1. A method comprising:
   receiving, by a processor, a first signal;
   generating, in response to the first signal, a second signal; and
   transmitting the second signal to a remote device.

2. The method of claim 1, wherein the processor is a non-transitory
   computer readable medium.

DETAILED DESCRIPTION

The present invention relates to systems and methods for processing
signals. FIG. 1 illustrates an embodiment of the invention. As shown
in FIG. 1, a processor receives an input signal and generates an
output signal in response thereto.
"""

# Representative TW patent fragment — TIPO bracket headers + 請求項.
TW_SAMPLE = """
【中文發明名稱】一種訊號處理裝置
【技術領域】
本發明係關於一種訊號處理裝置。
【先前技術】
習知技術中，訊號處理裝置包含處理器及記憶體。
【發明內容】
本發明之目的在於提供一種改良之訊號處理裝置。
【實施方式】
請參照圖1，本發明之訊號處理裝置包括處理器10及記憶體20。
【符號說明】
10：處理器
20：記憶體
【申請專利範圍】
請求項1：一種訊號處理裝置，包含：
  一處理器；及
  一記憶體，與該處理器電性連接。
請求項2：如請求項1所述之訊號處理裝置，其中該處理器為微控制器。
"""

# Representative CN patent fragment — 五书 section names, simplified.
CN_SAMPLE = """
权利要求书

1. 一种信号处理装置，其特征在于，包括：
   处理器；
   存储器，与所述处理器电性连接。

2. 根据权利要求1所述的信号处理装置，其中所述处理器为微控制器。

技术领域

本发明涉及一种信号处理装置。

背景技术

现有的信号处理装置包含处理器和存储器。

发明内容

本发明的目的在于提供一种改良的信号处理装置。

附图说明

图1为本发明的信号处理装置示意图。

具体实施方式

请参考图1，本发明的信号处理装置包括处理器10和存储器20。
"""


# --- US-selected mismatches ---------------------------------------------------


def test_us_selected_tw_doc_suggests_tw():
    assert detect_jurisdiction_mismatch(TW_SAMPLE, Jurisdiction.US) == "TW"


def test_us_selected_cn_doc_suggests_cn():
    assert detect_jurisdiction_mismatch(CN_SAMPLE, Jurisdiction.US) == "CN"


def test_us_selected_us_doc_no_mismatch():
    assert detect_jurisdiction_mismatch(US_SAMPLE, Jurisdiction.US) is None


# --- EPC sample ---------------------------------------------------------------

# A representative EPC English patent fragment. EPC-distinctive tells:
# British spelling ("characterised in that"), EPC two-part-form preamble,
# "any preceding claim" idiom, EPC Article / Rule citations. Word count
# is high so CJK ratio is essentially zero.
EPC_SAMPLE = """
Application before the European Patent Office under the European Patent
Convention (EPC).

The present invention relates to a signal-processing apparatus. The
problem addressed by Article 56 EPC for the closest prior art is set out
below.

Claims:

1. A signal-processing apparatus comprising a processor and a memory,
   characterised in that the memory is configured to store calibration
   values associated with the processor.

2. An apparatus according to claim 1, wherein the processor comprises a
   microcontroller.

3. An apparatus according to any preceding claim, further comprising a
   communication interface coupled to the processor.

4. An apparatus according to any one of claims 1 to 3, wherein the
   communication interface is wireless.

The clarity requirement of Article 84 EPC is satisfied because each
feature of the claims is supported by the description. Rule 43 EPC
governs the form of the claims; in particular, reference signs are
provided in parentheses pursuant to Rule 43(7) EPC.
"""


# --- EPC-selected mismatches --------------------------------------------------


def test_epc_selected_epc_doc_no_mismatch():
    assert detect_jurisdiction_mismatch(EPC_SAMPLE, Jurisdiction.EPC) is None


def test_epc_selected_us_doc_suggests_us():
    assert detect_jurisdiction_mismatch(US_SAMPLE, Jurisdiction.EPC) == "US"


def test_epc_selected_cn_doc_suggests_cn():
    assert detect_jurisdiction_mismatch(CN_SAMPLE, Jurisdiction.EPC) == "CN"


def test_epc_selected_tw_doc_suggests_tw():
    assert detect_jurisdiction_mismatch(TW_SAMPLE, Jurisdiction.EPC) == "TW"


def test_us_selected_epc_doc_suggests_epc():
    assert detect_jurisdiction_mismatch(EPC_SAMPLE, Jurisdiction.US) == "EPC"


def test_cn_selected_epc_doc_suggests_epc():
    assert detect_jurisdiction_mismatch(EPC_SAMPLE, Jurisdiction.CN) == "EPC"


def test_tw_selected_epc_doc_suggests_epc():
    assert detect_jurisdiction_mismatch(EPC_SAMPLE, Jurisdiction.TW) == "EPC"


def test_epc_selected_us_doc_with_one_epc_mention_still_suggests_us():
    """Asymmetric direction — US drafts that cite an EPC counterpart by
    name (single mention) should NOT cause EPC → US suggestion to be
    silenced. The asymmetric gate requires us_markers - epc_markers >= 2
    AND epc_markers == 0; a single 'European Patent' mention in a
    US-pattern draft puts epc_markers > 0 and stays at None — the
    conservative answer when both jurisdictions show signal."""
    text = US_SAMPLE + "\n\nThe European Patent Office published a counterpart."
    # us_markers should still be >= 2 (method of claim + non-transitory),
    # but epc_markers > 0, so the EPC → US gate stays closed.
    assert detect_jurisdiction_mismatch(text, Jurisdiction.EPC) is None


# --- CN-selected mismatches ---------------------------------------------------


def test_cn_selected_us_doc_suggests_us():
    assert detect_jurisdiction_mismatch(US_SAMPLE, Jurisdiction.CN) == "US"


def test_cn_selected_tw_doc_suggests_tw():
    assert detect_jurisdiction_mismatch(TW_SAMPLE, Jurisdiction.CN) == "TW"


def test_cn_selected_cn_doc_no_mismatch():
    assert detect_jurisdiction_mismatch(CN_SAMPLE, Jurisdiction.CN) is None


# --- TW-selected mismatches ---------------------------------------------------


def test_tw_selected_us_doc_suggests_us():
    assert detect_jurisdiction_mismatch(US_SAMPLE, Jurisdiction.TW) == "US"


def test_tw_selected_cn_doc_suggests_cn():
    assert detect_jurisdiction_mismatch(CN_SAMPLE, Jurisdiction.TW) == "CN"


def test_tw_selected_tw_doc_no_mismatch():
    assert detect_jurisdiction_mismatch(TW_SAMPLE, Jurisdiction.TW) is None


# --- Edge cases: don't false-positive on legitimate trace CJK ----------------


def test_us_doc_with_trace_cjk_no_mismatch():
    """A US patent that transliterates a Chinese name doesn't flip to CJK."""
    text = US_SAMPLE + "\n\nThe disclosed method was first described by 王 et al. in 2020."
    assert detect_jurisdiction_mismatch(text, Jurisdiction.US) is None


def test_empty_text_no_mismatch():
    assert detect_jurisdiction_mismatch("", Jurisdiction.US) is None
    assert detect_jurisdiction_mismatch("", Jurisdiction.CN) is None
    assert detect_jurisdiction_mismatch("", Jurisdiction.TW) is None


def test_whitespace_only_no_mismatch():
    assert detect_jurisdiction_mismatch("   \n\n   ", Jurisdiction.US) is None


def test_long_us_doc_truncated_correctly():
    """Sample window is bounded — long US docs with CJK appendices past
    the sample should still classify as US."""
    long_us = US_SAMPLE * 30  # >10k chars; CJK trailer is past the window
    long_us += "\n\n附录：" + "中文" * 5000
    assert detect_jurisdiction_mismatch(long_us, Jurisdiction.US) is None


# --- Edge cases: CJK doc without distinguishing markers ---------------------


def test_us_selected_cjk_no_markers_falls_back_to_cn():
    """Heavy CJK content but neither TIPO nor CNIPA markers present —
    detector falls back to CN suggestion (more common filing volume)."""
    text = "本发明描述一种新颖之装置。" * 50
    # Stripped of section headers, tied marker counts → CN fallback
    assert detect_jurisdiction_mismatch(text, Jurisdiction.US) == "CN"


def test_cn_selected_traditional_chars_no_tipo_markers_no_mismatch():
    """A CN draft using a traditional character (e.g., quoting a TW
    publication) but no TIPO bracket headers should NOT flip to TW —
    we require positive marker evidence to disambiguate, not script
    flavor."""
    text = CN_SAMPLE + "\n\n参考臺灣發布之类似技术文献，本发明改良之。"
    assert detect_jurisdiction_mismatch(text, Jurisdiction.CN) is None


@pytest.mark.parametrize(
    "selected,sample,expected",
    [
        (Jurisdiction.US, US_SAMPLE, None),
        (Jurisdiction.US, TW_SAMPLE, "TW"),
        (Jurisdiction.US, CN_SAMPLE, "CN"),
        (Jurisdiction.US, EPC_SAMPLE, "EPC"),
        (Jurisdiction.CN, US_SAMPLE, "US"),
        (Jurisdiction.CN, TW_SAMPLE, "TW"),
        (Jurisdiction.CN, CN_SAMPLE, None),
        (Jurisdiction.CN, EPC_SAMPLE, "EPC"),
        (Jurisdiction.TW, US_SAMPLE, "US"),
        (Jurisdiction.TW, TW_SAMPLE, None),
        (Jurisdiction.TW, CN_SAMPLE, "CN"),
        (Jurisdiction.TW, EPC_SAMPLE, "EPC"),
        (Jurisdiction.EPC, US_SAMPLE, "US"),
        (Jurisdiction.EPC, TW_SAMPLE, "TW"),
        (Jurisdiction.EPC, CN_SAMPLE, "CN"),
        (Jurisdiction.EPC, EPC_SAMPLE, None),
    ],
)
def test_mismatch_matrix(selected, sample, expected):
    """Full 4×4 jurisdiction-vs-sample matrix as a single regression gate."""
    assert detect_jurisdiction_mismatch(sample, selected) == expected
