# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
"""Tests for TW specification-support analysis (ADR-138, 專利法 §26 第3項)."""

from __future__ import annotations

from patentlint.analysis.tw_spec_support import (
    _build_inventory,
    _collect_spec_text,
    _collect_symbol_names,
    _has_interior_reject,
    _has_leading_reject,
    _is_boilerplate,
    _normalize_for_spec_support_tw,
    _recover_from_midphrase_prefix,
    _split_on_conjunction,
    _strip_spec_support_trailing_tokens,
    _strip_trailing_conjunction,
    _strip_trailing_predicate_before_marker,
    _tier3_char_window,
    attach_cross_references_tw,
    check_spec_support_tw,
)
from patentlint.models import (
    Claim,
    SymbolEntry,
    TwPatentDocument,
    UnsupportedTerm,
)


def _make_claim(cid: int, text: str, independent: bool = True, deps=None) -> Claim:
    return Claim(
        id=cid,
        text=text,
        independent=independent,
        method_claim=False,
        dependencies=deps or [],
    )


def _make_doc(
    *,
    claims: list[Claim] | None = None,
    disclosure: list[str] | None = None,
    embodiment: list[str] | None = None,
    technical_field: list[str] | None = None,
    prior_art: list[str] | None = None,
    symbol_table: list[SymbolEntry] | None = None,
    representative_drawing_symbols: list[SymbolEntry] | None = None,
) -> TwPatentDocument:
    return TwPatentDocument(
        claims=claims or [],
        disclosure=disclosure or [],
        embodiment=embodiment or [],
        technical_field=technical_field or [],
        prior_art=prior_art or [],
        symbol_table=symbol_table or [],
        representative_drawing_symbols=representative_drawing_symbols or [],
    )


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------


class TestNormalizeForSpecSupport:
    """_normalize_for_spec_support_tw: claim-side normalization."""

    def test_reference_form_prefix_stripped(self):
        assert _normalize_for_spec_support_tw("該基板") == "基板"
        assert _normalize_for_spec_support_tw("所述基板") == "基板"
        assert _normalize_for_spec_support_tw("前述基板") == "基板"

    def test_leading_preposition_stripped(self):
        assert _normalize_for_spec_support_tw("於所述基板") == "基板"
        assert _normalize_for_spec_support_tw("到所述第一電子裝置") == "第一電子裝置"
        assert _normalize_for_spec_support_tw("在該容器本體") == "容器本體"

    def test_quantifier_stripped(self):
        assert _normalize_for_spec_support_tw("一上壁部") == "上壁部"
        assert _normalize_for_spec_support_tw("一個容器本體") == "容器本體"
        assert _normalize_for_spec_support_tw("複數外齒狀結構") == "外齒狀結構"

    def test_trailing_parenthetical_numeral_stripped(self):
        assert _normalize_for_spec_support_tw("容器本體(100)") == "容器本體"
        assert _normalize_for_spec_support_tw("第一長度(L1)") == "第一長度"
        # Full-width parens
        assert _normalize_for_spec_support_tw("第一銜接部（222）") == "第一銜接部"

    def test_midphrase_reference_prefix_recovered(self):
        assert _normalize_for_spec_support_tw("有所述高亮度區域") == "高亮度區域"
        assert _normalize_for_spec_support_tw("個所述電子元件") == "電子元件"

    def test_trailing_conjunction_stripped(self):
        assert _normalize_for_spec_support_tw("顏色與") == "顏色"
        assert _normalize_for_spec_support_tw("內環結構與") == "內環結構"

    def test_trailing_clause_token_stripped(self):
        assert _normalize_for_spec_support_tw("間距介於") == "間距"
        assert _normalize_for_spec_support_tw("最低點位於") == "最低點"

    def test_paren_exposed_by_verb_strip(self):
        """端透過樞軸(2221)連: strip trailing 連, then strip exposed (2221)."""
        assert _normalize_for_spec_support_tw("端透過樞軸(2221)連") == "端透過樞軸"

    def test_empty_input_returns_empty(self):
        assert _normalize_for_spec_support_tw("") == ""

    def test_no_change_when_already_clean(self):
        assert _normalize_for_spec_support_tw("蓋組件") == "蓋組件"
        assert _normalize_for_spec_support_tw("帶蓋容器") == "帶蓋容器"


class TestRecoverFromMidphrasePrefix:
    def test_suffix_after_midphrase_所述(self):
        assert _recover_from_midphrase_prefix("有所述高亮度區域") == "高亮度區域"

    def test_suffix_after_midphrase_該(self):
        assert _recover_from_midphrase_prefix("解鎖指令至該通訊模組") == "通訊模組"

    def test_position_zero_prefix_left_intact(self):
        # Position 0 is handled upstream; this helper only fires on interior.
        assert _recover_from_midphrase_prefix("所述基板") == "所述基板"

    def test_no_prefix_unchanged(self):
        assert _recover_from_midphrase_prefix("蓋組件") == "蓋組件"


class TestStripTrailingConjunction:
    def test_trailing_與_stripped(self):
        assert _strip_trailing_conjunction("顏色與") == "顏色"

    def test_trailing_及_stripped(self):
        assert _strip_trailing_conjunction("X及") == "X"

    def test_trailing_以及_stripped_before_及(self):
        # _TW_CONJUNCTIONS order matters: 以及 tested before 及 to avoid
        # leaving a stray 以 after 及 strips.
        assert _strip_trailing_conjunction("組件以及") == "組件"

    def test_no_conjunction_unchanged(self):
        assert _strip_trailing_conjunction("蓋組件") == "蓋組件"


class TestStripSpecSupportTrailingTokens:
    def test_介於_stripped(self):
        assert _strip_spec_support_trailing_tokens("間距介於") == "間距"

    def test_位於_stripped(self):
        assert _strip_spec_support_trailing_tokens("最低點位於") == "最低點"

    def test_iterative_strip(self):
        # 彼此間隔地設 is longest-first in the denylist, so single pass suffices.
        assert _strip_spec_support_trailing_tokens("第一凹槽彼此間隔地設") == "第一凹槽"

    def test_no_strip_when_at_floor(self):
        # A 2-char term with a trailing 1-char token would go to empty; prevent.
        assert _strip_spec_support_trailing_tokens("相") == "相"

    # R7 (2026-05-29): comparison-verb trailing strips. Issues #106/
    # #108/#130/#133 - `大於`/`小於` mirror the existing `超過` entry.
    def test_大於_stripped(self):
        assert _strip_spec_support_trailing_tokens("通道寬度大於") == "通道寬度"

    def test_大於_stripped_after_leading_有(self):
        assert _strip_spec_support_trailing_tokens("有通道寬度大於") == "有通道寬度"

    def test_小於_stripped(self):
        assert _strip_spec_support_trailing_tokens("寬度小於") == "寬度"

    def test_大於_stripped_on_longer_head(self):
        assert _strip_spec_support_trailing_tokens("最大外徑大於") == "最大外徑"

    # 2026-06-05 batch (issues #187 / #193 / #194): trailing verbal /
    # adverbial tails over-captured past the head noun.
    def test_共同地_adverb_stripped(self):
        assert _strip_spec_support_trailing_tokens("夾持部共同地") == "夾持部"

    def test_可通訊地_adverb_stripped(self):
        # #187 - once the adverb is stripped, the head noun matches the spec
        # via substring even with an embedded reference numeral.
        assert (
            _strip_spec_support_trailing_tokens("檢體採集支援系統可通訊地")
            == "檢體採集支援系統"
        )

    def test_緊靠_verb_stripped(self):
        assert _strip_spec_support_trailing_tokens("夾持部緊靠") == "夾持部"

    def test_不平行_predicate_stripped(self):
        assert _strip_spec_support_trailing_tokens("第一外側壁不平行") == "第一外側壁"

    def test_2026_06_05_tokens_do_not_touch_legit_nouns(self):
        """FN guard - real nouns ending in the same characters stay intact.
        The adverb/verb tokens are multi-char and the verb fires only when
        the term ENDS in the verb, so 緊靠部/緊靠面 (ending 部/面) are safe."""
        for noun in ("土地", "基地", "場地", "緊靠部", "緊靠面", "平行板"):
            assert _strip_spec_support_trailing_tokens(noun) == noun


class TestSplitOnConjunction:
    def test_split_on_及(self):
        parts = _split_on_conjunction("定子組件及轉子組件")
        assert "定子組件" in parts
        assert "轉子組件" in parts

    def test_split_on_以及(self):
        parts = _split_on_conjunction("讀取單元以及磁性環")
        assert "讀取單元" in parts
        assert "磁性環" in parts

    def test_no_conjunction_single_element(self):
        assert _split_on_conjunction("蓋組件") == ["蓋組件"]

    def test_too_short_side_not_split(self):
        # Right side < _MIN_INVENTORY_LENGTH, don't split
        assert _split_on_conjunction("組件及A") == ["組件及A"]

    def test_multi_conjunction_recursive_split(self):
        # Audit finding: walker captures like 定子及轉子以及軸承 must split
        # all three ways, not just at the first qualifying conjunction.
        assert _split_on_conjunction("定子及轉子以及軸承") == ["定子", "轉子", "軸承"]
        assert _split_on_conjunction("組件A及組件B以及組件C") == ["組件A", "組件B", "組件C"]

    def test_multi_conjunction_mixed_short_side(self):
        # If one sub-split has a side shorter than min-length, that sub-split
        # stays joined while the others split. Returns the longest valid
        # decomposition.
        result = _split_on_conjunction("大前提及小前提以及結論")
        assert "大前提" in result
        assert "小前提" in result
        assert "結論" in result


# ---------------------------------------------------------------------------
# Stoplists & rejects
# ---------------------------------------------------------------------------


class TestLeadingReject:
    def test_suffix_only_char_rejected(self):
        assert _has_leading_reject("部互") is True
        assert _has_leading_reject("端面") is True
        assert _has_leading_reject("埠口") is True

    def test_verb_phrase_rejected(self):
        assert _has_leading_reject("顯示於該") is True
        assert _has_leading_reject("描述該個人化特") is True
        assert _has_leading_reject("經選擇") is True

    def test_legit_noun_accepted(self):
        assert _has_leading_reject("容器本體") is False
        assert _has_leading_reject("蓋組件") is False
        assert _has_leading_reject("第一電極") is False

    def test_朝往_adverb_rejected(self):
        # #246: 朝往 ("toward") is an adverb captured standalone.
        assert _has_leading_reject("朝往") is True
        assert _has_leading_reject("朝向角度") is False  # FN guard

    def test_中兩_stranded_fragment_rejected(self):
        # #194: `相鄰的其中兩個` → walker dropped `其`, leaving `中兩個`.
        # Mirror of `中一`. Real nouns (中央/中心) don't start `中兩`.
        assert _has_leading_reject("中兩個") is True
        assert _has_leading_reject("中央處理器") is False


class TestInteriorReject:
    def test_超過_in_clause_rejected(self):
        assert _has_interior_reject("扭力超過一預定扭力值") is True

    def test_彼此_rejected(self):
        assert _has_interior_reject("第一凹槽彼此間隔") is True

    def test_clean_noun_accepted(self):
        assert _has_interior_reject("預定扭力值") is False

    def test_coupling_predicate_rejected(self):
        """Issue #76: `<verb>一<noun>` coupling predicate is a clause."""
        assert _has_interior_reject("第一端耦接一輸入電壓") is True
        assert _has_interior_reject("控制端連接一負載") is True

    def test_互相_adverb_clause_rejected(self):
        # #248: 面且互相正交 is a predicate clause; 互相 ("mutually") adverb.
        assert _has_interior_reject("面且互相正交") is True
        assert _has_interior_reject("互鎖機構") is False  # FN guard
        assert _has_interior_reject("相互作用") is False  # FN guard

    def test_coupling_noun_compound_accepted(self):
        """`耦接器` / `連接部` (no `一`) are real nouns - not rejected."""
        assert _has_interior_reject("耦接器") is False
        assert _has_interior_reject("連接部") is False


class TestSpecSupportMethodClauseFP:
    """Method-claim over-capture FPs from the 2026-05-21 firm-draft
    queue (issues #69/#76/#77/#78)."""

    def test_distributive_quantifier_stripped(self):
        # #77: `電壓各` → `各` trailing-stripped → clean head `電壓`.
        assert _strip_spec_support_trailing_tokens("電壓各") == "電壓"

    def test_process_verb_stripped(self):
        # #69: `兩端減薄` → `減薄` process verb trailing-stripped.
        assert _strip_spec_support_trailing_tokens("兩端減薄") == "兩端"

    def test_prepositional_fragment_rejected(self):
        # #69: `介由使用…` prepositional connector - leading reject.
        assert _has_leading_reject("介由使用半導體材料") is True

    def test_qizhong_fragment_rejected(self):
        # #78: `中一個` stranded `其中一個` connective - leading reject.
        assert _has_leading_reject("中一個") is True


class TestBoilerplate:
    def test_exact_match(self):
        assert _is_boilerplate("前述") is True
        assert _is_boilerplate("複數") is True
        assert _is_boilerplate("如請求項") is True

    def test_prefix_match(self):
        # Walker-captured extensions of boilerplate phrases.
        assert _is_boilerplate("如請求項4至請求項10") is True

    def test_legit_term_not_boilerplate(self):
        assert _is_boilerplate("蓋組件") is False


# ---------------------------------------------------------------------------
# Spec-text + symbol collection
# ---------------------------------------------------------------------------


class TestCollectSpecText:
    def test_concatenates_four_body_subsections(self):
        doc = _make_doc(
            technical_field=["技術領域段落"],
            prior_art=["先前技術段落"],
            disclosure=["發明內容段落"],
            embodiment=["實施方式段落"],
        )
        text = _collect_spec_text(doc)
        assert "技術領域段落" in text
        assert "先前技術段落" in text
        assert "發明內容段落" in text
        assert "實施方式段落" in text

    def test_excludes_drawings_description_and_symbol_table(self):
        # drawings_description and symbol_table are not exposed in
        # _collect_spec_text; we simulate by leaving them out of _make_doc
        # and confirming the concatenation only includes the 4 sections.
        doc = _make_doc(technical_field=["A"], embodiment=["B"])
        assert _collect_spec_text(doc) == "A\nB"


class TestCollectSymbolNames:
    def test_symbol_table_names_collected(self):
        doc = _make_doc(symbol_table=[
            SymbolEntry(numeral="10", name="基板"),
            SymbolEntry(numeral="20", name="蓋體"),
        ])
        names = _collect_symbol_names(doc)
        assert "基板" in names
        assert "蓋體" in names

    def test_representative_drawing_symbols_unioned(self):
        doc = _make_doc(
            symbol_table=[SymbolEntry(numeral="10", name="基板")],
            representative_drawing_symbols=[SymbolEntry(numeral="1", name="帶蓋容器")],
        )
        names = _collect_symbol_names(doc)
        assert "基板" in names
        assert "帶蓋容器" in names

    def test_empty_entry_names_excluded(self):
        doc = _make_doc(symbol_table=[SymbolEntry(numeral="10", name="")])
        assert _collect_symbol_names(doc) == set()


# ---------------------------------------------------------------------------
# Inventory build
# ---------------------------------------------------------------------------


class TestBuildInventory:
    def test_intro_captured_and_normalized(self):
        claims = [_make_claim(1, "一種裝置，包含：一基板。")]
        inv = _build_inventory(claims)
        terms = [t for _, t in inv]
        assert "基板" in terms

    def test_dedup_across_claims(self):
        claims = [
            _make_claim(1, "一種裝置，包含：一基板。"),
            _make_claim(2, "如請求項1之裝置，其中該基板包括一塗層。", independent=False, deps=[1]),
        ]
        inv = _build_inventory(claims)
        terms = [t for _, t in inv]
        # 基板 appears only once (dedup). 塗層 captured from claim 2.
        assert terms.count("基板") == 1

    def test_length_cap_rejects_long_clause(self):
        # 13-char clause exceeds _MAX_INVENTORY_LENGTH=12
        long_clause = "一應用程式上設定其他該行動裝置或帳號"
        claims = [_make_claim(1, f"一種方法，包含：{long_clause}。")]
        inv = _build_inventory(claims)
        terms = [t for _, t in inv]
        # Nothing from that clause should survive the length cap.
        assert not any(len(t) > 12 for t in terms)


# ---------------------------------------------------------------------------
# Tier-level behavior
# ---------------------------------------------------------------------------


class TestTier0SymbolTable:
    def test_term_in_symbol_table_passes(self):
        claims = [_make_claim(1, "一種裝置，包含：一基板。")]
        doc = _make_doc(
            claims=claims,
            symbol_table=[SymbolEntry(numeral="10", name="基板")],
            # No body sections - Tier 0 should short-circuit before Tier 1.
        )
        result = check_spec_support_tw(doc)
        assert result == []

    def test_term_in_representative_drawing_symbols_passes(self):
        # Both intros (容器 + 帶蓋容器) must be supported: 容器 via the
        # body disclosure, 帶蓋容器 via the representative-drawing legend.
        claims = [_make_claim(1, "一種容器，包含：一帶蓋容器。")]
        doc = _make_doc(
            claims=claims,
            embodiment=["本容器為金屬製。"],
            representative_drawing_symbols=[SymbolEntry(numeral="1", name="帶蓋容器")],
        )
        result = check_spec_support_tw(doc)
        assert result == []


class TestTier1NormalizedExact:
    def test_bare_noun_matches_prefixed_in_spec(self):
        # Claim term 基板 (normalized) is a substring of 該基板 in spec.
        claims = [_make_claim(1, "一種裝置，包含：一基板。")]
        doc = _make_doc(claims=claims, embodiment=["該基板設置於底座。"])
        result = check_spec_support_tw(doc)
        assert result == []

    def test_prefixed_claim_term_matches_bare_spec(self):
        # Claim has 該基板 (normalized to 基板); spec has bare 基板.
        claims = [_make_claim(1, "一種裝置，包含：一基板，該基板具有一塗層。")]
        doc = _make_doc(claims=claims, embodiment=["基板由金屬製成。塗層為陶瓷。"])
        result = check_spec_support_tw(doc)
        assert result == []

    def test_unsupported_term_flagged(self):
        claims = [_make_claim(1, "一種裝置，包含：一量子糾纏模組。")]
        doc = _make_doc(claims=claims, embodiment=["本裝置具有處理器與記憶體。"])
        result = check_spec_support_tw(doc)
        phrases = [ut.phrase for ut in result]
        assert "量子糾纏模組" in phrases


class TestTier3CharWindow:
    def test_all_bigrams_within_window_match(self):
        # "第二交線" bigrams {第二, 二交, 交線} all within 30 chars of each other
        # in a sentence that mentions them in proximity.
        assert _tier3_char_window(
            "第二交線",
            "其中第二外齒狀結構的第二交線與第一外齒狀結構對稱。",
        ) is True

    def test_bigrams_scattered_fail(self):
        # Each bigram appears far apart - over 30 chars separation.
        spec = "第二" + "A" * 40 + "交線"
        assert _tier3_char_window("第二交線", spec) is False

    def test_missing_bigram_fails_early(self):
        assert _tier3_char_window("量子糾纏", "本裝置具有處理器與記憶體。") is False


# ---------------------------------------------------------------------------
# End-to-end with stoplists
# ---------------------------------------------------------------------------


class TestStoplistFiltering:
    def test_generic_term_filtered(self):
        claims = [_make_claim(1, "一種系統。")]
        doc = _make_doc(claims=claims, embodiment=["其他描述。"])
        result = check_spec_support_tw(doc)
        # 系統 is in _TW_GENERIC_TERMS → not emitted.
        assert result == []

    def test_boilerplate_like_如請求項_filtered(self):
        # Walker might capture 如請求項X; boilerplate prefix-match filters it.
        # We test the helper directly since constructing the exact walker
        # intro for this is fragile.
        assert _is_boilerplate("如請求項4至請求項10") is True


# ---------------------------------------------------------------------------
# attach_cross_references_tw
# ---------------------------------------------------------------------------


class TestAttachCrossReferencesTw:
    def test_both_directions_annotated(self):
        antecedent = [{"claim_id": 2, "term": "基板"}]
        unsupported = [UnsupportedTerm(claim_number=2, phrase="基板")]
        attach_cross_references_tw(antecedent, unsupported)
        assert antecedent[0].get("cross_ref") == "spec_support"
        assert unsupported[0].cross_ref == "antecedent"

    def test_no_match_no_mutation(self):
        antecedent = [{"claim_id": 2, "term": "基板"}]
        unsupported = [UnsupportedTerm(claim_number=3, phrase="塗層")]
        attach_cross_references_tw(antecedent, unsupported)
        assert "cross_ref" not in antecedent[0] or antecedent[0]["cross_ref"] is None
        assert unsupported[0].cross_ref is None

    def test_different_claim_id_no_cross_ref(self):
        antecedent = [{"claim_id": 1, "term": "基板"}]
        unsupported = [UnsupportedTerm(claim_number=2, phrase="基板")]
        attach_cross_references_tw(antecedent, unsupported)
        assert "cross_ref" not in antecedent[0] or antecedent[0]["cross_ref"] is None
        assert unsupported[0].cross_ref is None


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEmptyAndMinimalDocs:
    def test_no_claims_empty_result(self):
        doc = _make_doc(claims=[])
        assert check_spec_support_tw(doc) == []

    def test_claim_with_no_intros_empty_result(self):
        # Claim body with only references, no 一X intros.
        claims = [_make_claim(1, "該基板。")]
        doc = _make_doc(claims=claims, embodiment=["基板。"])
        result = check_spec_support_tw(doc)
        assert result == []

    def test_empty_spec_term_flagged(self):
        claims = [_make_claim(1, "一種裝置，包含：一特殊元件。")]
        doc = _make_doc(claims=claims)
        result = check_spec_support_tw(doc)
        phrases = [ut.phrase for ut in result]
        assert "特殊元件" in phrases


class TestSpecSupportRound202607:
    """2026-07 TW spec-support over-capture round (#321/#333/#334/#335/#342/
    #343/#344/#348/#350/#351)."""

    def test_321_conjunction_after_token_strip(self):
        # A trailing token (位於) re-exposes a dangling 及 → re-strip collapses it.
        assert _normalize_for_spec_support_tw("鎖定部及位於") == "鎖定部"

    def test_333_lingwai_leading_reject(self):
        assert _has_leading_reject("另外兩個") is True
        assert _has_leading_reject("另一實施例") is False  # FN-guard

    def test_334_meige_boilerplate(self):
        assert _is_boilerplate("每個") is True
        assert _is_boilerplate("每一彈性臂") is True

    def test_335_neiao_formation_predicate(self):
        assert _strip_trailing_predicate_before_marker(
            "第二擋牆內凹", "由第二擋牆內凹形成的結構"
        ) == "第二擋牆"
        # nominal X內凹的 (followed by 的) is untouched
        assert _strip_trailing_predicate_before_marker(
            "第二擋牆內凹", "第二擋牆內凹的表面"
        ) == "第二擋牆內凹"

    def test_342_de_yi_and_cardinal_measure(self):
        assert _normalize_for_spec_support_tw("第二晶粒的一第二晶圓") == "第二晶圓"
        assert _normalize_for_spec_support_tw("垂直堆疊晶粒組二個") == "垂直堆疊晶粒組"
        # FN-guards: nouns that merely contain 個 / 的 are unaffected
        assert _normalize_for_spec_support_tw("整個殼體") == "整個殼體"
        assert _normalize_for_spec_support_tw("十字接頭") == "十字接頭"

    def test_343_dacheng_trailing_verb(self):
        assert _normalize_for_spec_support_tw("導電材料達成") == "導電材料"

    def test_344_leading_method_verb_yi(self):
        assert _normalize_for_spec_support_tw("提供一導線框架") == "導線框架"
        assert _normalize_for_spec_support_tw("設置一第二導電元件") == "第二導電元件"
        # FN-guards: coverb 設置於 and genuine nouns untouched
        assert _normalize_for_spec_support_tw("設置面") == "設置面"
        assert _normalize_for_spec_support_tw("提供者") == "提供者"

    def test_348_yixiang_leading_reject(self):
        assert _has_leading_reject("以向一水體樣本") is True
        assert _has_leading_reject("以太網路") is False  # FN-guard
        assert _has_leading_reject("向量") is False  # FN-guard

    def test_350_stranded_quantifier_recover_left(self):
        assert _split_on_conjunction("第一基板及一個") == ["第一基板"]
        # FN-guard: short non-quantifier residue stays whole
        assert _split_on_conjunction("組件及A") == ["組件及A"]

    def test_351_leading_ref_marker_strip(self):
        assert _normalize_for_spec_support_tw("各所述天線") == "天線"


class TestSpecSupportRoundR34:
    """R34 TW spec-support over-capture round (#439/#440/#441/#442/#443) -
    one firm drafter's planar-transformer draft."""

    def test_439_442_leading_baokuo_baohan(self):
        # Leading transitional verb 包括/包含 stripped so the head noun surfaces.
        assert _normalize_for_spec_support_tw("包括一第一平板") == "第一平板"
        assert _normalize_for_spec_support_tw("包含一第一磁柱體") == "第一磁柱體"
        # FN-guards: real nouns opening with 包 (but not 包括/包含) are untouched.
        assert _normalize_for_spec_support_tw("包覆層") == "包覆層"
        assert _normalize_for_spec_support_tw("包裝結構") == "包裝結構"

    def test_440_trailing_xianglin(self):
        # 相鄰 ("adjacent to") trailing relational verb stripped.
        assert _normalize_for_spec_support_tw("第二次級繞組層相鄰") == "第二次級繞組層"
        # FN-guard: a positional element carries a noun head (相鄰區), untouched.
        assert _normalize_for_spec_support_tw("相鄰區") == "相鄰區"

    def test_441_stranded_short_left_split(self):
        # A sub-2-char left before 及 (區, stranded from 設置區) is dropped;
        # the clean coordinate noun is kept.
        assert _split_on_conjunction("區及一第二次級繞組") == ["第二次級繞組"]
        # FN-guards: a ≥2-char left splits normally; a short non-quantifier
        # RIGHT residue (model letter) stays whole (#350).
        assert _split_on_conjunction("第一基板及第二基板") == ["第一基板", "第二基板"]
        assert _split_on_conjunction("組件及A") == ["組件及A"]

    def test_443_trailing_locative_clause(self):
        # Interior 於/在 + determiner opens a locative predicate → strip the tail.
        assert _normalize_for_spec_support_tw("第二電源轉換器於一次") == "第二電源轉換器"
        assert _normalize_for_spec_support_tw("第一開關電路在一表面") == "第一開關電路"
        # FN-guard: 在 NOT followed by a determiner is part of the noun and the
        # gate (idx≥2, next char a determiner) leaves 內在電阻 intact.
        assert _normalize_for_spec_support_tw("內在電阻") == "內在電阻"

    def test_r36_leading_fragment_strips(self):
        # #495 - a leading nominalizer 者 (from 至少一者) plus the verb 形成
        # unwind in one pass, leaving the real element name.
        assert _normalize_for_spec_support_tw("者形成外露表面") == "外露表面"
        # #496 - a leading 且 blocks the position-0 reference-prefix strip;
        # removing it lets 所述 come off, and the 沿 locative clause is cut.
        assert _normalize_for_spec_support_tw("且所述彈性封邊部沿所述片") == "彈性封邊部"
        # #482/#486 - the measure word 筆 stranded by the 至少一 quantifier strip.
        assert _normalize_for_spec_support_tw("筆比賽資料") == "比賽資料"
        # #483/#487 - 任 + cardinal is quantifier scaffolding, never an element.
        assert _normalize_for_spec_support_tw("任兩個") == ""
        # FN-guards: the residual floor keeps 形成層 whole, the 筆-lexeme set
        # keeps 筆記型電腦 whole, and 任務 has no cardinal after 任.
        assert _normalize_for_spec_support_tw("形成層") == "形成層"
        assert _normalize_for_spec_support_tw("筆記型電腦") == "筆記型電腦"
        assert _normalize_for_spec_support_tw("任務地圖模組") == "任務地圖模組"

    def test_r36_leading_rejects(self):
        # #467 關於 (preposition) and #482/#486 有至少 (quantifier scaffolding).
        assert _has_leading_reject("關於該病") is True
        assert _has_leading_reject("有至少一") is True
        # FN-guards: single-char 有 is still unconstrained.
        assert _has_leading_reject("有機層") is False
        assert _has_leading_reject("關節模組") is False

    def test_r36_interior_cuts(self):
        # #494 - 至少 is a quantifier adverb; the head before it is the element.
        assert _normalize_for_spec_support_tw("孔隙至少部") == "孔隙"
        # #485/#488 - 用以 opens a function clause; the capture ends in the
        # clause's own object (使 of the following 使用者), so only an interior
        # cut can reach it.
        assert _normalize_for_spec_support_tw("按鈕用以提供使") == "按鈕"

    def test_r36_yong_before_yi_gate(self):
        # #485/#488 - a trailing 用 the noun scan glued on from 用以.
        claim = "所述比賽資訊顯示裝置還包含多個按鈕，多個所述按鈕用以提供使用者按壓。"
        assert _normalize_for_spec_support_tw("按鈕用", claim) == "按鈕"
        # FN-guard 1: without the following 以 in the claim, no strip.
        assert _normalize_for_spec_support_tw("按鈕用", "多個所述按鈕用於按壓。") == "按鈕用"
        # FN-guard 2: a lexicalized 用-final word is never reached, even with
        # a following 以 (the TW gold corpus carries 弧作用 as legit).
        assert _normalize_for_spec_support_tw("弧作用", "該弧作用以產生電漿。") == "弧作用"

    def test_440_f1_TP_preserved(self):
        # The confirmed-defect finding (#440-f1) must still be inventoried.
        claim = _make_claim(
            2,
            "如請求項1所述的平板變壓器，其中該多層電路板更包括一第一輔助初級繞組層，"
            "該第一輔助初級繞組層與該第一初級繞組層並聯連接，且該第一輔助初級繞組層與"
            "該些次級繞組層中的一第二次級繞組層相鄰設置。",
            independent=False,
            deps=[1],
        )
        inv = [t for _, t in _build_inventory([claim])]
        assert "第一輔助初級繞組層" in inv
        # And the over-captures are gone.
        assert "第二次級繞組層相鄰" not in inv
