# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Copyright (c) 2025-2026 Christopher Chen
#
# Generates the Part 5 (Assessment 2, Filing-Ready) learner files:
#   every-word-counts/files/part-5-filing-ready/Filing-Ready-Draft-Self-Watering-Planter.docx
#   every-word-counts/files/part-5-filing-ready/Note-to-a-Colleague-Template.docx
#
# Not part of the site build (which uses only Node built-ins). Run by hand when
# the case changes:  python3 course/materials/make_part5_files.py
# Needs python-docx and Pillow.
#
# The draft deliberately contains 10 planted problems. The answer key lives in
# every-word-counts/pages.mjs (route part-5-filing-ready/answer-key). Keep the
# two in step: change a planted problem here, change the key there.

import io
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[1] / 'every-word-counts' / 'files' / 'part-5-filing-ready'
OUT.mkdir(parents=True, exist_ok=True)

FONT = 'Times New Roman'


def base_doc(title):
    d = Document()
    st = d.styles['Normal']
    st.font.name = FONT
    st.font.size = Pt(12)
    st.element.rPr.rFonts.set(qn('w:eastAsia'), 'PMingLiU')
    st.paragraph_format.line_spacing = 1.5
    st.paragraph_format.space_after = Pt(6)
    for name in ('Heading 1', 'Heading 2'):
        h = d.styles[name]
        h.font.name = FONT
        h.font.color.rgb = RGBColor(0, 0, 0)
        h.element.rPr.rFonts.set(qn('w:eastAsia'), 'PMingLiU')
    d.styles['Heading 1'].font.size = Pt(14)
    d.styles['Heading 2'].font.size = Pt(12)
    d.core_properties.title = title
    d.core_properties.author = 'Every Word Counts (course practice file)'
    d.core_properties.language = 'en-US'
    for s in d.sections:
        s.top_margin = s.bottom_margin = Inches(1)
        s.left_margin = s.right_margin = Inches(1)
    return d


n = 0


def para(d, text, numbered=True):
    global n
    p = d.add_paragraph()
    if numbered:
        n += 1
        p.add_run(f'[{n:04d}]\t')
        p.paragraph_format.first_line_indent = Inches(0)
    p.add_run(text)
    return p


def page_break(d):
    d.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def drawing_png():
    W, H = 1400, 1100
    im = Image.new('RGB', (W, H), 'white')
    g = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf', 34)
        fb = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf', 40)
    except OSError:
        f = fb = ImageFont.load_default()
    k = 4
    # outer housing 12
    g.line([(300, 250), (340, 950), (900, 950), (940, 250)], fill='black', width=k)
    # ledge 28
    g.line([(330, 640), (420, 640)], fill='black', width=k)
    g.line([(820, 640), (910, 640)], fill='black', width=k)
    # inner pot 16
    g.line([(400, 230), (430, 640), (810, 640), (840, 230)], fill='black', width=k)
    # soil hatch
    for x in range(440, 800, 40):
        g.line([(x, 360), (x + 30, 330)], fill='black', width=2)
    # water surface in reservoir 14
    for y in (760, 800):
        for x in range(350, 890, 50):
            g.arc([x, y, x + 50, y + 20], 0, 180, fill='black', width=2)
    # bottom opening 30 and wick 18
    g.rectangle([600, 625, 640, 655], fill='white', outline='white')
    g.line([(610, 420), (610, 900)], fill='black', width=k)
    g.line([(630, 420), (630, 900)], fill='black', width=k)
    # fill tube 20
    g.line([(860, 180), (860, 880)], fill='black', width=k)
    g.line([(890, 180), (890, 880)], fill='black', width=k)
    # overflow hole 26
    g.ellipse([925, 700, 945, 720], outline='black', width=k)
    # float 32 and window 34
    g.rectangle([360, 740, 410, 790], outline='black', width=k)
    g.rectangle([325, 720, 345, 830], outline='black', width=k)
    # drainage tray 24
    g.line([(300, 1000), (310, 1030), (930, 1030), (940, 1000)], fill='black', width=k)

    def label(num, xy, to):
        g.line([xy, to], fill='black', width=2)
        g.text((xy[0] + (8 if xy[0] > to[0] else -70), xy[1] - 20), str(num), font=f, fill='black')

    label(10, (1100, 120), (940, 250))
    label(12, (1100, 450), (925, 450))
    label(14, (1100, 820), (880, 810))
    label(16, (150, 300), (410, 300))
    label(18, (150, 470), (610, 470))
    label(20, (1100, 200), (890, 200))
    label(22, (150, 880), (330, 800))
    label(24, (1100, 1040), (930, 1030))
    label(26, (1100, 650), (945, 710))
    label(28, (150, 640), (330, 640))
    label(30, (150, 560), (600, 640))
    label(32, (150, 760), (360, 765))
    label(34, (150, 940), (335, 830))
    g.text((W // 2 - 60, H - 60), 'FIG. 1', font=fb, fill='black')
    buf = io.BytesIO()
    im.save(buf, 'PNG')
    buf.seek(0)
    return buf


def set_alt(shape, text):
    docpr = shape._inline.docPr
    docpr.set('descr', text)
    docpr.set('title', 'FIG. 1')


def draft():
    global n
    n = 0
    d = base_doc('Filing-Ready draft: Self-Watering Planter (practice file)')

    note = d.add_paragraph()
    note.add_run('Practice file for Every Word Counts, Part 5 (Assessment 2). '
                 'This is a fictional application. Inventors: Lin Mei-Hua and Samuel Okoye. '
                 'Applicant: Verdant Loop Co., Ltd. Turn on Track Changes before you edit.').italic = True
    note.paragraph_format.line_spacing = 1.15

    d.add_heading('SELF-WATERING PLANTER', level=1)

    d.add_heading('BACKGROUND', level=2)
    para(d, 'Potted plants need regular watering. People who travel or who forget to water their plants '
            'often lose them to dry soil, while people who water too often can drown the roots.')
    para(d, 'Some planters hold extra water in a tray under the pot. These trays must be refilled often, and it '
            'is hard to tell how much water is left without lifting the pot.')

    d.add_heading('SUMMARY', level=2)
    para(d, 'A self-watering planter has an outer housing with a water reservoir in its lower portion and an '
            'inner pot supported above the reservoir. A wick draws water from the reservoir up into the soil in '
            'the inner pot, so the soil stays evenly moist for days or weeks. In some embodiments, a water-level '
            'indicator shows how much water is left.')

    # PLANTED 1: Detailed Description placed before Brief Description of the Drawings (37 CFR 1.77(b)).
    d.add_heading('DETAILED DESCRIPTION', level=2)
    para(d, 'Referring to FIG. 1, a self-watering planter 10 includes an outer housing 12, a water reservoir 14, '
            'an inner pot 16, and a wick 18. The outer housing 12 may be made of molded plastic, ceramic, or '
            'another waterproof material.')
    para(d, 'The water reservoir 14 is formed in a lower portion of the outer housing 12. In some examples, the '
            'water reservoir 14 holds between 0.5 and 2 liters of water. An overflow hole 26 in the outer housing '
            '12 is positioned at a top of the water reservoir 14 so that excess water drains out instead of '
            'flooding the inner pot 16.')
    para(d, 'The inner pot 16 rests on a ledge 28 inside the outer housing 12, above the water reservoir 14. The '
            'inner pot 16 has a bottom opening 30. The wick 18 extends through the bottom opening 30 from the '
            'water reservoir 14 into the soil in the inner pot 16. The wick 18 may be made of cotton or polyester '
            'fiber and may have a width of 5 to 15 millimeters.')
    # PLANTED 4: reservoir called 16 here; 16 is the inner pot (37 CFR 1.84(p)(4)).
    para(d, 'A fill tube 20 extends from a top of the outer housing 12 down into the water reservoir 16. The fill '
            'tube 20 may have an inner diameter of at least 10 millimeters so that a user can refill the water '
            'reservoir 14 without lifting the inner pot 16.')
    para(d, 'In some embodiments, the planter 10 further includes a water-level indicator 22. The water-level '
            'indicator 22 has a float 32 disposed in the water reservoir 14 and a window 34 formed in the outer '
            'housing 12. The float 32 rises and falls with the water. A colored top of the float 32 is visible '
            'through the window 34.')
    # PLANTED 5: same part called "feed strip" (37 CFR 1.71(a)).
    para(d, 'As the soil in the inner pot 16 dries, the feed strip 18 draws water upward from the water reservoir '
            '14 by capillary action.')
    para(d, 'In some embodiments, the planter 10 further includes a drainage tray 24 removably attached to a '
            'bottom of the outer housing 12. The drainage tray 24 catches water that leaves through the overflow '
            'hole 26.')
    para(d, 'The embodiments described above are examples. Changes in shape, size, and materials may be made '
            'without departing from the scope of the claims.')

    d.add_heading('BRIEF DESCRIPTION OF THE DRAWINGS', level=2)
    para(d, 'FIG. 1 is a cross-sectional side view of a self-watering planter according to an embodiment.')

    # PLANTED 3: no page break before the claims (37 CFR 1.75(h)).
    d.add_heading('CLAIMS', level=2)
    d.add_paragraph('What is claimed is:')
    claims = [
        # PLANTED 10: "consisting of" while the specification describes optional extra parts
        # and later claims add parts (MPEP 2111.03). Expected action: flag, not fix.
        ('1', 'A self-watering planter, consisting of:\n'
              'an outer housing;\n'
              'a water reservoir formed in a lower portion of the outer housing;\n'
              'an inner pot supported in the outer housing above the water reservoir, the inner pot having a '
              'bottom opening; and\n'
              'a wick extending through the bottom opening from the water reservoir into the inner pot.'),
        ('2', 'The self-watering planter of claim 1, wherein the wick is made of cotton or polyester fiber.'),
        # PLANTED 6: "the drainage tray" has no antecedent (MPEP 2173.05(e)).
        ('3', 'The self-watering planter of claim 1, wherein the drainage tray is removably attached to a bottom '
              'of the outer housing.'),
        # PLANTED 7: depends on a later claim (35 U.S.C. 112(d); MPEP 608.01(n)).
        ('4', 'The self-watering planter of claim 8, wherein the float has a colored top that is visible through '
              'the window.'),
        ('5', 'The self-watering planter of claim 1, wherein the outer housing has an overflow hole positioned at '
              'a top of the water reservoir.'),
        # PLANTED 8: numbering skips 6 (37 CFR 1.75(f)).
        # PLANTED 9: two sentences (MPEP 608.01(m)).
        ('7', 'The self-watering planter of claim 1, further comprising a fill tube extending from a top of the '
              'outer housing into the water reservoir. The fill tube has an inner diameter of at least 10 '
              'millimeters.'),
        ('8', 'The self-watering planter of claim 1, further comprising a water-level indicator having a float '
              'disposed in the water reservoir and a window formed in the outer housing.'),
        ('9', 'The self-watering planter of claim 2, wherein the wick has a width of 5 to 15 millimeters.'),
    ]
    for num, text in claims:
        lines = text.split('\n')
        p = d.add_paragraph()
        p.add_run(f'{num}.\t{lines[0]}')
        for ln in lines[1:]:
            q = d.add_paragraph(ln)
            q.paragraph_format.left_indent = Inches(0.5)

    page_break(d)
    d.add_heading('ABSTRACT', level=2)
    # PLANTED 2: about 180 words; 37 CFR 1.72(b) prefers 150 or fewer.
    d.add_paragraph(
        'A self-watering planter for indoor and outdoor plants is disclosed. The planter includes an outer housing '
        'made of molded plastic, ceramic, or another waterproof material, and a water reservoir formed in a lower '
        'portion of the outer housing that holds between 0.5 and 2 liters of water. An inner pot rests on a ledge '
        'inside the outer housing above the water reservoir and has a bottom opening. A wick made of cotton or '
        'polyester fiber, with a width of 5 to 15 millimeters, extends through the bottom opening from the water '
        'reservoir into the soil in the inner pot and draws water upward by capillary action as the soil dries, '
        'so that the soil stays evenly moist for days or weeks without daily watering. A fill tube with an inner '
        'diameter of at least 10 millimeters lets a user refill the water reservoir without lifting the inner pot. '
        'An overflow hole at the top of the water reservoir lets excess water drain out instead of flooding the '
        'inner pot. In some embodiments, a water-level indicator with a float and a window shows how much water '
        'is left, and a removable drainage tray attached to the bottom of the outer housing catches water that '
        'leaves through the overflow hole.')

    page_break(d)
    d.add_heading('DRAWINGS', level=2)
    pic = d.add_picture(drawing_png(), width=Inches(6))
    set_alt(d.inline_shapes[-1],
            'FIG. 1, cross-sectional side view. Reference numerals: 10 planter; 12 outer housing; 14 water '
            'reservoir; 16 inner pot; 18 wick; 20 fill tube; 22 water-level indicator; 24 drainage tray; '
            '26 overflow hole; 28 ledge; 30 bottom opening; 32 float; 34 window.')
    d.add_paragraph('Reference numerals (text version of FIG. 1): 10 planter · 12 outer housing · 14 water '
                    'reservoir · 16 inner pot · 18 wick · 20 fill tube · 22 water-level indicator · 24 drainage '
                    'tray · 26 overflow hole · 28 ledge · 30 bottom opening · 32 float · 34 window')
    d.save(OUT / 'Filing-Ready-Draft-Self-Watering-Planter.docx')


def shade(cell, fill):
    tcPr = cell._tc.get_or_add_tcPr()
    s = OxmlElement('w:shd')
    s.set(qn('w:val'), 'clear'); s.set(qn('w:color'), 'auto'); s.set(qn('w:fill'), fill)
    tcPr.append(s)


def mark_header(row):
    trPr = row._tr.get_or_add_trPr()
    h = OxmlElement('w:tblHeader'); h.set(qn('w:val'), 'true'); trPr.append(h)
    for c in row.cells:
        shade(c, 'E3F2FA')
        for r in c.paragraphs[0].runs:
            r.bold = True


def template():
    d = base_doc('Note to a colleague: template (Every Word Counts, Part 5)')
    d.styles['Normal'].paragraph_format.line_spacing = 1.15
    d.add_heading('Note to a colleague', level=1)
    p = d.add_paragraph()
    p.add_run('About 150 words, in English. Explain your three most important changes so your reader can act '
              'on them without asking you. For each one: what you changed, why it matters, and the rule.').italic = True
    d.add_paragraph('To (name a role, e.g., the drafter, the filing team, a client liaison): ')
    d.add_paragraph('From: ')
    d.add_paragraph('About: Self-Watering Planter draft')
    for i in (1, 2, 3):
        d.add_heading(f'Change {i}', level=2)
        d.add_paragraph('What I changed (and where): ')
        d.add_paragraph('Why it matters: ')
        d.add_paragraph('Rule: ')
    d.add_heading('Optional: change log', level=2)
    d.add_paragraph('Use this table instead of Track Changes if that works better for you, for example with a '
                    'screen reader. It counts the same. Add rows as needed.')
    t = d.add_table(rows=4, cols=4)
    t.style = 'Table Grid'
    for c, h in zip(t.rows[0].cells, ['Where (paragraph or claim)', 'Original text', 'Correction or flag', 'Rule']):
        c.text = h
    mark_header(t.rows[0])
    d.save(OUT / 'Note-to-a-Colleague-Template.docx')


if __name__ == '__main__':
    draft()
    template()
    print('wrote', sorted(p.name for p in OUT.iterdir()))
