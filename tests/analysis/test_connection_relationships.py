# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025–2026 Christopher Chen
"""Tests for patentlint.analysis.connection_relationships.

Covers the shared check applied to both TW and CN claim sets via the
two pre-built configs. Tests use the public ``check_connection_relationships``
entry point with synthetic ``Claim`` objects — no fixture .docx loading.
"""

from patentlint.analysis.connection_relationships import (
    _CN_CONNECTION_CONFIG,
    _TW_CONNECTION_CONFIG,
    check_connection_relationships,
)
from patentlint.models import Claim


def _claim(id: int, text: str, *, independent: bool = True) -> Claim:
    return Claim(id=id, text=text, independent=independent)


# ── TW: positive (flag) cases ────────────────────────────────────────────


class TestTwPositive:
    def test_bare_list_no_verb_flagged(self):
        text = (
            "一種裝置，包括："
            "一第一單元；"
            "一第二單元；"
            "以及一第三單元。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].details_params["claim_id"] == 1
        assert results[0].details_params["component_count"] >= 3
        assert results[0].reference == "專利審查基準 第二篇第一章 §2.4"

    def test_zhipu_three_components_no_verb(self):
        text = (
            "一種設備，具備："
            "一第一模組；一第二模組；以及一第三模組。"
        )
        results = check_connection_relationships([_claim(2, text)], _TW_CONNECTION_CONFIG)
        assert len(results) == 1
        assert results[0].status == "verify"

    def test_quoted_reference_form_flagged(self):
        # 引用記載型式 — 具備 is a transition phrase, not a connection verb.
        text = (
            "一種帶蓋容器，"
            "具備如請求項1所述之蓋組件、以及一容器本體。"
        )
        results = check_connection_relationships([_claim(3, text)], _TW_CONNECTION_CONFIG)
        assert len(results) == 1
        assert results[0].status == "verify"


# ── TW: negative (no flag) cases ─────────────────────────────────────────


class TestTwNegative:
    def test_verb_present_passes(self):
        text = (
            "一種遊戲控制器，包括："
            "一第一手柄主體；"
            "一第二手柄主體，與所述第一手柄主體互相連接；"
            "以及一功能擴充模組，設置於所述第一手柄主體上。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_extended_verb_passes(self):
        text = (
            "一種裝置，包括："
            "一第一構件，鄰接於一第二構件；"
            "以及一第三構件。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_method_claim_skipped(self):
        text = (
            "一種訊號處理方法，包括："
            "接收一第一訊號；"
            "處理一第二訊號；"
            "以及輸出一結果。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_composition_claim_skipped(self):
        text = (
            "一種高頻基板用樹脂組成物，其包括："
            "20重量份至70重量份的聚苯醚樹脂；"
            "5重量份至40重量份的聚丁二烯樹脂；"
            "以及20重量份至45重量份的交聯劑。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_mpf_claim_skipped(self):
        text = (
            "一種裝置，包括："
            "一第一手段，用以儲存資料；"
            "一第二手段，用以處理資料；"
            "以及一第三手段，用以輸出資料。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_crm_claim_skipped(self):
        text = (
            "一種電腦可讀儲存媒體，其上儲存有："
            "一第一指令集；"
            "以及一第二指令集。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_dependent_claim_skipped(self):
        text = "如請求項1所述之裝置，其中包括第一單元、第二單元以及第三單元。"
        results = check_connection_relationships(
            [_claim(2, text, independent=False)], _TW_CONNECTION_CONFIG
        )
        assert results[0].status == "pass"

    def test_single_component_no_flag(self):
        text = "一種裝置，包括一單元，該單元能夠處理訊號。"
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_empty_claims_list_passes(self):
        results = check_connection_relationships([], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"


# ── CN: positive (flag) cases ────────────────────────────────────────────


class TestCnPositive:
    def test_bare_list_no_verb_flagged(self):
        text = (
            "一种装置，包括："
            "一第一单元；"
            "一第二单元；"
            "以及一第三单元。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].details_params["claim_id"] == 1
        assert results[0].reference == "审查指南 第二部分 第二章 §3.2.1"

    def test_two_components_no_verb_flagged(self):
        text = "一种系统，包含：一处理模块；以及一存储模块。"
        results = check_connection_relationships([_claim(7, text)], _CN_CONNECTION_CONFIG)
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].details_params["component_count"] == 2


# ── CN: negative (no flag) cases ─────────────────────────────────────────


class TestCnNegative:
    def test_verb_present_passes(self):
        text = (
            "一种装置，包括："
            "一第一单元，连接于一第二单元；"
            "以及一第三单元，设置于所述第一单元上。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_method_claim_skipped(self):
        text = "一种数据处理方法，包括：获取数据；处理数据；以及输出结果。"
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_composition_claim_skipped(self):
        text = (
            "一种树脂组合物，包括："
            "20重量份的聚苯醚；"
            "10重量份的聚丁二烯；"
            "以及5重量份的交联剂。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_mpf_claim_skipped(self):
        text = (
            "一种装置，包括："
            "用于存储数据的手段；"
            "以及用于处理数据的手段。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_crm_claim_skipped(self):
        text = (
            "一种计算机可读存储介质，其上存储有："
            "第一指令集；以及第二指令集。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"


# ── Cross-claim aggregation ──────────────────────────────────────────────


class TestAggregation:
    def test_per_claim_emit_plus_pass(self):
        flagged = (
            "一種裝置，包括：一第一單元；一第二單元；以及一第三單元。"
        )
        passing = (
            "一種裝置，包括：一第一單元，連接於一第二單元；以及一第三單元。"
        )
        results = check_connection_relationships(
            [_claim(1, flagged), _claim(2, passing)],
            _TW_CONNECTION_CONFIG,
        )
        # Two flagged emit one verify; passing claim does not add a tile
        # (the aggregate pass tile is only emitted when nothing is flagged).
        assert len(results) == 1
        assert results[0].status == "verify"
        assert results[0].details_params["claim_id"] == 1

    def test_two_flagged_emit_two_items(self):
        c1 = "一種裝置，包括：一第一單元；一第二單元；以及一第三單元。"
        c2 = "一種設備，具備：一第一模組；以及一第二模組。"
        results = check_connection_relationships(
            [_claim(1, c1), _claim(2, c2)],
            _TW_CONNECTION_CONFIG,
        )
        assert len(results) == 2
        assert all(r.status == "verify" for r in results)
        assert {r.details_params["claim_id"] for r in results} == {1, 2}


# ── Regression: lexicon coverage of empirically-found structural verbs ───
#
# These cases were FPs in the initial implementation because the speculative
# verb seed list missed common drafter idioms. Added during the
# post-implementation real-corpus audit (TW spec1, CN BYD, etc.).


class TestExtendedLexiconCoverage:
    """Verbs added after Phase 0 corpus audit must keep these claims passing."""

    def test_tw_she_you_setting_construction(self):
        # 設有/安裝於 — TW spec1 C1 shape
        text = (
            "一種蓋組件，包括：一蓋本體；以及一蓋體，"
            "透過一鉸鏈部旋動自如地安裝於所述蓋本體；"
            "所述蓋本體包括：一外筒構件，上部設有一開口部。"
        )
        results = check_connection_relationships([_claim(1, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_tw_anzhuangyou_mounting(self):
        # 安裝有 — TW spec1 C10 shape (帶蓋容器)
        text = "一種帶蓋容器，具備如請求項1所述之蓋組件、以及安裝有所述蓋組件的一容器本體。"
        results = check_connection_relationships([_claim(10, text)], _TW_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_cn_kinematic_verbs(self):
        # 转动/移动/形成 — BYD CN213655447U C1 shape (folding mechanism)
        text = (
            "一种折叠机构，所述折叠机构包括两个屏幕支撑组件以及两个避让组件；"
            "每个所述屏幕支撑组件包括固定支撑板和活动支撑板；"
            "两个所述屏幕支撑组件能够分别绕避让组件转动；"
            "所述活动支撑板能够在所述固定支撑板和第一轴线之间移动。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"

    def test_cn_constructed_as(self):
        # 被构造为 — common in mechanical apparatus claims
        text = (
            "一种装置，包括：一第一构件；以及一第二构件，"
            "所述第二构件被构造为能够与所述第一构件配合。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "pass"


# ── Regression: continuation-prefix filter avoids over-counting ──────────


class TestComponentExtractionAccuracy:
    def test_sublist_intro_filtered(self):
        # "所述装置还包括：" is a sub-list intro, not a component.
        # Without the filter, it would inflate the component count.
        text = (
            "一种装置，包括：\n"
            "抽取模块，用于X；\n"
            "输入模块，用于Y；\n"
            "所述装置还包括：\n"
            "计算模块，用于Z。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        # Should still flag (3 modules, no verb), but count should be 3 not 4.
        assert results[0].status == "verify"
        assert results[0].details_params["component_count"] == 3

    def test_qizhong_continuation_filtered(self):
        # "其中，..." sub-clauses describe function, not new components.
        text = (
            "一种系统，包括：\n"
            "处理单元，用于A；\n"
            "存储单元，用于B；\n"
            "其中，所述处理单元和所述存储单元用于完成任务。"
        )
        results = check_connection_relationships([_claim(1, text)], _CN_CONNECTION_CONFIG)
        assert results[0].status == "verify"
        assert results[0].details_params["component_count"] == 2
