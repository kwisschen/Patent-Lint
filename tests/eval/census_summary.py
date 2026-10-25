# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# census_summary.py PRE POST CENSUS - one-screen summary of a walker change:
# silenced keys by gold verdict, the silenced legit/coverage list, and every
# UNPAIRED-NEW key (a new key on a claim where nothing was silenced).
# PRE/POST are validate_fix snapshots; CENSUS is silenced_census.py output.
# Wave E (2026-10-25) used it after every trial.
import json
import re
import sys
from collections import Counter
pre = {tuple(x) for x in json.load(open(sys.argv[1]))}
post = {tuple(x) for x in json.load(open(sys.argv[2]))}
census = open(sys.argv[3]).read().splitlines()
sil, new = pre - post, post - pre
verd = Counter()
for line in census:
    m = re.match(r"SILENCED (\S+) ", line)
    if m:
        verd[m.group(1)] += 1
silc = {(k[0], k[1]) for k in sil}
unp = sorted(k for k in new if (k[0], k[1]) not in silc)
print(f"silenced {len(sil)} {dict(verd)}  new {len(new)}  paired-new {len(new) - len(unp)}  UNPAIRED-NEW {len(unp)}")
for line in census:
    if line.startswith(("SILENCED legit", "SILENCED coverage")):
        print("  " + line[:160])
for k in unp:
    print("  UNP", k)
