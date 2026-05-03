"""Gate 1 reproducer for tonight's walker_fp candidates from triage.

Per `triage-report` skill §5b Gate 1: synthesize a minimal fixture from the
diagnostic context windows, feed through the walker, check whether it
reproduces the same finding shape (term + check_key + approximate offset).

Tonight's targets — 4 unanimous walker_fp verdicts on TW spec_support and
1 walker_fp on TW antecedentBasis from issues #19, #20, #21, #23, #24:

specSupport function-word fragments (4 findings, 2 unique phrases):
  - `較前述矽層在前述` (issues #20, #24)
  - `對在` (issues #21, #24)

antecedentBasis 前述-marker miss (2 findings, 1 unique pattern):
  - `各p型通道層` with reference_form `前述各p型通道層` (issue #19)
  - `各n型通道層` with reference_form `前述各n型通道層` (issue #23)
"""

from __future__ import annotations

import sys
from pathlib import Path

PATENTLINT_ROOT = Path("/Users/chrischen/Documents/Projects/Patent-Lint")
sys.path.insert(0, str(PATENTLINT_ROOT / "src"))

from patentlint.analysis.tw_claims import check_antecedent_basis  # noqa: E402
from patentlint.analysis.tw_spec_support import check_spec_support_tw  # noqa: E402
from patentlint.models import Claim, TwPatentDocument  # noqa: E402


def make_claim(cid: int, text: str, deps=None) -> Claim:
    return Claim(
        id=cid,
        text=text,
        independent=(deps is None or not deps),
        method_claim=False,
        dependencies=deps or [],
    )


def make_doc(claims, disclosure=None, embodiment=None) -> TwPatentDocument:
    return TwPatentDocument(
        claims=claims,
        disclosure=disclosure or [],
        embodiment=embodiment or [],
        technical_field=[],
        prior_art=[],
        symbol_table=[],
        representative_drawing_symbols=[],
    )


# Fixtures synthesized from the 30-char vicinity context in each user report.
# Each fixture preserves the surface form of the flagged term + enough surrounding
# context to keep the parser/walker plumbing happy. Spec sections are minimal
# (don't mention the flagged phrase) so the walker either fires or doesn't.

TESTS = [
    # ---- specSupport function-word fragments ----
    {
        "id": "specSupport_較前述矽層在前述",
        "source_issues": [20, 24],
        "walker": "spec_support",
        "expected_phrase": "較前述矽層在前述",
        "claims": [
            make_claim(
                1,
                "一種半導體裝置，包含一基板。",
            ),
            make_claim(
                5,
                # The flagged phrase IS in this claim — context_after from the user "p型電晶體之閘極長度方向"
                "如請求項1所述之半導體裝置，其中前述矽層被夾持，周端面構造成具有較前述矽層在前述p型電晶體之閘極長度方向。",
                deps=[1],
            ),
        ],
        "embodiment": ["本裝置之基板由矽材料製成。"],
    },
    {
        "id": "specSupport_對在",
        "source_issues": [21, 24],
        "walker": "spec_support",
        "expected_phrase": "對在",
        "claims": [
            make_claim(
                1,
                "一種半導體裝置，包含一基板。",
            ),
            make_claim(
                12,
                # Flagged phrase from context: 蝕刻使膜厚減少，並且形成對在前述矽層之間
                "如請求項1所述之半導體裝置，前述犧牲片層從露出面進行蝕刻使膜厚減少，並且形成對在前述矽層之間形成得較前述矽層更薄之區域。",
                deps=[1],
            ),
        ],
        "embodiment": ["本裝置之基板由矽材料製成。"],
    },
    # ---- antecedentBasis 前述各<noun> pattern ----
    {
        "id": "antecedentBasis_前述各p型通道層",
        "source_issues": [19],
        "walker": "antecedent",
        "expected_term": "各p型通道層",
        "expected_reference_form": "前述各p型通道層",
        "claims": [
            make_claim(
                1,
                # Synthesized from #19 finding3 context: 介隔著閘極絕緣膜覆蓋前述<term>之全周
                # The bug: walker fires on `各p型通道層` even though `前述` IS the antecedent marker.
                "一種半導體裝置，包含具備全周閘極構造之p型電晶體以及n型電晶體；前述p型電晶體具有各p型通道層；介隔著閘極絕緣膜覆蓋前述各p型通道層之全周。",
            ),
        ],
    },
]


def run_gate1():
    print(f"\n{'='*70}\nGate 1 Reproducer — tonight's walker_fp candidates\n{'='*70}\n")
    confirmed = []
    not_reproduced = []

    for t in TESTS:
        print(f"\n--- {t['id']}  (source issues: {t['source_issues']}) ---")
        doc = make_doc(claims=t["claims"], embodiment=t.get("embodiment"))

        if t["walker"] == "spec_support":
            findings = check_spec_support_tw(doc)
            phrases = [f.phrase for f in findings]
            print(f"  walker emitted {len(findings)} unsupported-term findings")
            print(f"  emitted phrases: {phrases}")
            if t["expected_phrase"] in phrases:
                print(f"  ✅ REPRODUCED: '{t['expected_phrase']}' in walker output")
                confirmed.append(t["id"])
            else:
                print(f"  ❌ NOT REPRODUCED: '{t['expected_phrase']}' NOT in walker output")
                # Check if any phrase contains the expected fragment
                contains = [p for p in phrases if t["expected_phrase"] in p or p in t["expected_phrase"]]
                if contains:
                    print(f"    (related phrases that DID emit: {contains})")
                not_reproduced.append(t["id"])

        elif t["walker"] == "antecedent":
            findings = check_antecedent_basis(doc)
            print(f"  walker emitted {len(findings)} antecedent findings")
            for f in findings:
                print(f"    - claim {f['claim_id']} term={f['term']!r} ref_form={f['reference_form']!r}")
            matched = [
                f for f in findings
                if f["term"] == t["expected_term"] and f["reference_form"] == t["expected_reference_form"]
            ]
            if matched:
                print(f"  ✅ REPRODUCED: term={t['expected_term']!r} ref_form={t['expected_reference_form']!r}")
                confirmed.append(t["id"])
            else:
                print(f"  ❌ NOT REPRODUCED: expected term={t['expected_term']!r} ref_form={t['expected_reference_form']!r}")
                not_reproduced.append(t["id"])

    print(f"\n{'='*70}\nSUMMARY\n{'='*70}")
    print(f"Confirmed (Gate 1 PASSED): {len(confirmed)}/{len(TESTS)}")
    for c in confirmed:
        print(f"  ✅ {c}")
    print(f"Not reproduced: {len(not_reproduced)}/{len(TESTS)}")
    for n in not_reproduced:
        print(f"  ❌ {n}")

    print()
    print("Walker-round trigger check (per skill §post-closeout-posture):")
    spec_support_confirmed = sum(1 for c in confirmed if "specSupport" in c)
    antecedent_confirmed = sum(1 for c in confirmed if "antecedentBasis" in c)
    print(f"  TW spec_support confirmed walker_fps: {spec_support_confirmed}")
    print(f"  TW antecedent confirmed walker_fps: {antecedent_confirmed}")
    if spec_support_confirmed >= 3:
        print("  ✅ TW spec_support meets ≥3 trigger threshold — walker-round invocation candidate")
    if antecedent_confirmed >= 3:
        print("  ✅ TW antecedent meets ≥3 trigger threshold")


if __name__ == "__main__":
    run_gate1()
