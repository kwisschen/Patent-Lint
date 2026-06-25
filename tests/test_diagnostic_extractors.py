# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Per-script context-window sanity for the report-modal preview.

These values are a privacy-facing contract: the modal preview shows the
user every fragment that will be sent. Changing the window size silently
would change what users see, so the per-script values are pinned here.
"""

from patentlint.diagnostic_extractors import (
    ANCESTOR_WINDOW_HAN,
    ANCESTOR_WINDOW_LATIN,
    CONTEXT_WINDOW_HAN,
    CONTEXT_WINDOW_HANGUL,
    CONTEXT_WINDOW_JA,
    CONTEXT_WINDOW_LATIN,
    _ancestor_window_for,
    _context_window_for,
    _excerpt_around,
    _excerpt_around_reference,
    extract_antecedent_basis,
)


class TestExcerptAnchorsOnReference:
    """The diagnostic trail must anchor on the FLAGGED REFERENCE (所述X / the X),
    not the first mention (often the introduction) — issues #265/266/267."""

    def test_latin_anchors_on_reference_not_intro(self):
        # 'skin' introduced (bare) early, referenced as 'the skin' late.
        text = ("wherein the housing is attached to skin of a human body, "
                "and the light source faces the skin of the human body")
        before, after, off = _excerpt_around_reference(text, "skin", "the skin")
        # offset must land on the SECOND 'skin' (the reference), not the first
        assert off == text.rfind("skin")
        assert before.endswith("the ")  # the reference prefix precedes it

    def test_cjk_anchors_on_reference(self):
        text = "多個所述光源組沿一預設方向排列，並且所述預設方向與所述帶體不垂直"
        before, after, off = _excerpt_around_reference(text, "預設方向", "所述預設方向")
        # anchor on the 預設方向 inside 所述預設方向 (the reference), not the
        # first 預設方向 in 一預設方向排列
        assert off == text.find("所述預設方向") + len("所述")
        assert before.endswith("所述")

    def test_fallback_to_last_occurrence_when_reference_form_absent(self):
        text = "a widget here and the widget there"
        before, after, off = _excerpt_around_reference(text, "widget", None)
        assert off == text.rfind("widget")

    def test_missing_term_returns_none(self):
        assert _excerpt_around_reference("nothing here", "absent", "the absent") == (None, None, None)


class TestContextWindowForScript:
    def test_latin_english(self):
        assert _context_window_for("A user interface comprising the user device.") == CONTEXT_WINDOW_LATIN

    def test_latin_german_with_umlauts(self):
        assert _context_window_for("Eine Benutzeroberfläche umfassend das Gerät.") == CONTEXT_WINDOW_LATIN

    def test_han_traditional_chinese(self):
        assert _context_window_for("一種使用者介面，包括該使用者裝置。") == CONTEXT_WINDOW_HAN

    def test_han_simplified_chinese(self):
        assert _context_window_for("一种用户界面装置，包括所述用户装置。") == CONTEXT_WINDOW_HAN

    def test_japanese_kana_presence_wins(self):
        # Mixed Han + kana — kana presence routes to JA window
        assert _context_window_for("ユーザインターフェースであって、前記ユーザ装置を備える。") == CONTEXT_WINDOW_JA

    def test_japanese_kanji_heavy_with_some_kana(self):
        # Predominantly kanji but with hiragana particles — still JA
        assert _context_window_for("前記ユーザ装置を備えることを特徴とする。") == CONTEXT_WINDOW_JA

    def test_hangul_korean(self):
        assert _context_window_for("사용자 인터페이스로서, 상기 사용자 장치가 표시되는 것을 특징으로 한다.") == CONTEXT_WINDOW_HANGUL

    def test_empty(self):
        assert _context_window_for("") == CONTEXT_WINDOW_LATIN

    def test_stray_cjk_in_latin_falls_back_to_latin(self):
        assert _context_window_for("user interface 裝置 displayed on browser") == CONTEXT_WINDOW_LATIN

    def test_chinese_with_one_stray_kana_does_not_misroute(self):
        # Edge case: CN claim that quotes a single Japanese product
        # name. Threshold of 3 kana chars protects against misrouting.
        assert _context_window_for("一种装置，引用ソ产品的设计。") == CONTEXT_WINDOW_HAN


class TestExcerptHonorsPerScriptWindow:
    def test_han_window_is_smaller(self):
        zh = "一種使用者介面，包括該使用者裝置顯示於該瀏覽程式上。"
        before, after, _ = _excerpt_around(zh, "該使用者裝置")
        assert before is not None and len(before) <= CONTEXT_WINDOW_HAN
        assert after is not None and len(after) <= CONTEXT_WINDOW_HAN

    def test_japanese_window_is_18(self):
        ja = "本発明はユーザインターフェースであって、前記ユーザ装置を備えることを特徴とする発明である。"
        before, after, _ = _excerpt_around(ja, "前記ユーザ装置")
        assert before is not None and len(before) <= CONTEXT_WINDOW_JA
        assert after is not None and len(after) <= CONTEXT_WINDOW_JA

    def test_latin_window_keeps_full_30(self):
        en = "A user interface comprising the user device displayed on the browser opening the page above."
        before, after, _ = _excerpt_around(en, "user device")
        assert before is not None and len(before) <= CONTEXT_WINDOW_LATIN
        assert after is not None and len(after) <= CONTEXT_WINDOW_LATIN

    def test_explicit_override_wins(self):
        en = "A" * 100 + "TARGET" + "B" * 100
        before, after, _ = _excerpt_around(en, "TARGET", before=5, after=5)
        assert before == "AAAAA"
        assert after == "BBBBB"

    def test_case_insensitive_find_slices_from_original(self):
        en = "Configured To Control Electrostatic Energy Discharged"
        before, after, off = _excerpt_around(
            en, "electrostatic energy", before=12, after=12,
            case_insensitive=True,
        )
        # match located case-insensitively, window sliced original-cased
        assert off == en.lower().find("electrostatic energy")
        assert "Control" in before  # original casing preserved, not lowered
        assert after == " Discharged"


class TestAncestorWindowTier:
    """The ancestor-introduction excerpt uses a deliberately smaller
    second window tier — it only reveals the introduction's grammatical
    shape and exposes a second claim's prose, so it must stay tight."""

    def test_ancestor_window_is_smaller_than_child(self):
        assert ANCESTOR_WINDOW_LATIN < CONTEXT_WINDOW_LATIN
        assert ANCESTOR_WINDOW_HAN < CONTEXT_WINDOW_HAN

    def test_ancestor_window_per_script(self):
        assert _ancestor_window_for("configured to control the circuit") == ANCESTOR_WINDOW_LATIN
        assert _ancestor_window_for("一種雙向靜電放電保護電路其中放電電路") == ANCESTOR_WINDOW_HAN


class TestAncestorBasisEnrichment:
    """Parent-claim diagnostic on antecedent-basis findings — the bit
    that splits a walker FP from a genuine §112 gap in an anonymous
    child-claim report."""

    def _finding(self, **kw):
        base = {
            "claim_id": 5,
            "term": "electrostatic energy",
            "reference_form": "the electrostatic energy",
            "claim_text": "The circuit of claim 1, wherein the electrostatic energy is discharged.",
            "suggested_match": None,
        }
        base.update(kw)
        return base

    def test_term_found_in_ancestor_emits_window(self):
        f = self._finding(
            ancestor_claim_ids=[1],
            ancestor_match_claim_id=1,
            ancestor_match_text=(
                "An ESD circuit configured to control electrostatic "
                "energy discharged from the control node."
            ),
        )
        out = extract_antecedent_basis([f], total_claims=5)["findings"][0]
        assert out["term_in_ancestor_text"] is True
        assert out["ancestor_match_claim_id"] == 1
        # window reveals the verb preceder, bounded to the Latin tier
        assert "control" in out["ancestor_context_before"]
        assert len(out["ancestor_context_before"]) <= ANCESTOR_WINDOW_LATIN

    def test_term_absent_from_ancestor_is_false(self):
        f = self._finding(
            ancestor_claim_ids=[1],
            ancestor_match_claim_id=None,
            ancestor_match_text=None,
        )
        out = extract_antecedent_basis([f], total_claims=5)["findings"][0]
        assert out["term_in_ancestor_text"] is False
        assert out["ancestor_context_before"] is None

    def test_full_ancestor_text_never_reaches_payload(self):
        # Sentinel placed far from the term — well outside the bounded
        # ancestor window — so a leak would mean the full text shipped.
        secret = (
            "An ESD circuit SENTINEL_PROSE having very many intervening "
            "words of claim prose configured to control electrostatic energy."
        )
        f = self._finding(
            ancestor_claim_ids=[1], ancestor_match_claim_id=1,
            ancestor_match_text=secret,
        )
        out = extract_antecedent_basis([f], total_claims=5)["findings"][0]
        assert "ancestor_match_text" not in out
        assert "SENTINEL_PROSE" not in str(out)

    def test_walker_without_ancestor_data_omits_block(self):
        # A walker finding that doesn't supply ancestor keys must not get a
        # misleading term_in_ancestor_text:false — the block is omitted
        # entirely. (US/CN/TW walkers all supply the keys in production; a
        # bare synthetic finding here does not.)
        out = extract_antecedent_basis([self._finding()], total_claims=5)["findings"][0]
        assert "term_in_ancestor_text" not in out
        assert "ancestor_claim_ids" not in out


class TestTermEarlierInClaimEnrichment:
    """Same-claim earlier-introduction signal (2026-06-09). Splits a
    walker FP (term introduced earlier in the SAME claim, article-less /
    verb-object, but missed by the intro extractor) from a genuine §112
    gap — the same-claim sibling of term_in_ancestor_text. Reported users
    said "same claim introduces X already" (#206/#207 US, #221/#224/#225
    CN)."""

    def test_term_introduced_earlier_in_same_claim_true(self):
        # 'eyes' is mentioned article-less ("having eyes") before the
        # flagged definite reference ("the eyes") in the same claim.
        f = {
            "claim_id": 9,
            "term": "eyes",
            "reference_form": "the eyes",
            "claim_text": (
                "The method of claim 1, comprising obtaining facial images "
                "having eyes of multiple persons; extracting features of "
                "gazing behaviors of the eyes."
            ),
            "suggested_match": None,
        }
        out = extract_antecedent_basis([f], total_claims=9)["findings"][0]
        assert out["term_earlier_in_claim"] is True

    def test_term_earlier_in_same_claim_cjk_true(self):
        # CN: 控制指令 introduced (发送控制指令) before the reference 该控制指令.
        f = {
            "claim_id": 1,
            "term": "控制指令",
            "reference_form": "该控制指令",
            "claim_text": (
                "一种方法，包括：通过主机发送控制指令至显示器，"
                "其中该控制指令用于切换显示。"
            ),
            "suggested_match": None,
        }
        out = extract_antecedent_basis([f], total_claims=1)["findings"][0]
        assert out["term_earlier_in_claim"] is True

    def test_term_not_earlier_when_only_the_reference_present(self):
        # A genuine missing-antecedent: the term appears only once (the
        # flagged reference). No earlier mention → False.
        f = {
            "claim_id": 2,
            "term": "special widget",
            "reference_form": "the special widget",
            "claim_text": "The device of claim 1, wherein the special widget rotates.",
            "suggested_match": None,
        }
        out = extract_antecedent_basis([f], total_claims=2)["findings"][0]
        assert out["term_earlier_in_claim"] is False

    def test_over_capture_garbage_term_is_false(self):
        # An over-captured clause fragment that does not recur earlier
        # stays False (won't mislabel a real over-capture FP as introduced).
        f = {
            "claim_id": 1,
            "term": "目标影像输入端口发送控制",
            "reference_form": "该目标影像输入端口发送控制",
            "claim_text": (
                "一种方法，包括：通过主机从该目标影像输入端口发送控制指令至显示器。"
            ),
            "suggested_match": None,
        }
        out = extract_antecedent_basis([f], total_claims=1)["findings"][0]
        assert out["term_earlier_in_claim"] is False


class TestDidYouMeanSourceEnrichment:
    """Issue #70: a null `did_you_mean_claim_id` is ambiguous — surface
    `did_you_mean_source` + `term_in_symbol_table` so a symbol-table hit
    is distinguishable from a chain/morphological hit."""

    def _finding(self, **kw):
        base = {
            "claim_id": 2,
            "term": "背面側接觸子",
            "reference_form": "前述背面側接觸子",
            "claim_text": "如請求項1所述的裝置，其中前述背面側接觸子的寬度。",
        }
        base.update(kw)
        return base

    def test_symbol_table_source_surfaced(self):
        # The #70 shape: did-you-mean is an exact 符號說明 hit — no claim
        # id by design. `did_you_mean_source` makes that legible.
        f = self._finding(
            suggested_match={
                "term": "背面側接觸子", "claim_id": None,
                "source": "symbol_table",
            },
            term_in_symbol_table=True,
        )
        out = extract_antecedent_basis([f], total_claims=5)["findings"][0]
        assert out["did_you_mean_claim_id"] is None
        assert out["did_you_mean_source"] == "symbol_table"
        assert out["term_in_symbol_table"] is True

    def test_chain_source_is_null(self):
        # A chain DYM carries a claim id and no explicit source.
        f = self._finding(
            suggested_match={"term": "背面接觸子", "claim_id": 1},
            term_in_symbol_table=False,
        )
        out = extract_antecedent_basis([f], total_claims=5)["findings"][0]
        assert out["did_you_mean_source"] is None
        assert out["did_you_mean_claim_id"] == 1
        assert out["term_in_symbol_table"] is False

    def test_non_tw_finding_omits_symbol_table_field(self):
        # US/CN findings have no 符號說明 — the field is omitted, not False.
        f = {
            "claim_id": 2, "term": "widget", "reference_form": "the widget",
            "claim_text": "The apparatus wherein the widget is blue.",
            "suggested_match": None,
        }
        out = extract_antecedent_basis([f], total_claims=5)["findings"][0]
        assert "term_in_symbol_table" not in out
        assert out["did_you_mean_source"] is None
