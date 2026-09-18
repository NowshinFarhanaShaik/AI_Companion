"""Builds the PDF used by the eval suite and the demo seed.

Run from backend/:  python -m ai.evals.build_fixture
The generated file is committed, because PyMuPDF stamps each build with a
new document ID and the app de-duplicates uploads by file hash.
"""
from pathlib import Path

import pymupdf

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
FIXTURE_PDF = FIXTURE_DIR / "photosynthesis_notes.pdf"

PAGES: list[tuple[str, str]] = [
    (
        "1. What photosynthesis is",
        "Photosynthesis is the process by which plants, algae and some bacteria convert "
        "light energy into chemical energy stored in glucose. Organisms that do this are "
        "called autotrophs because they make their own food. The overall balanced equation "
        "is 6CO2 + 6H2O + light energy -> C6H12O6 + 6O2. In plants the process happens "
        "inside chloroplasts, which are most abundant in the mesophyll cells of leaves. "
        "Chloroplasts contain the green pigment chlorophyll, which absorbs mainly red and "
        "blue light and reflects green light, which is why leaves look green. Carbon dioxide "
        "enters the leaf through small pores called stomata, and water arrives from the roots "
        "through the xylem. Photosynthesis has two stages: the light-dependent reactions and "
        "the Calvin cycle.",
    ),
    (
        "2. The light-dependent reactions",
        "The light-dependent reactions take place in the thylakoid membranes of the "
        "chloroplast. Light is absorbed first by photosystem II and then by photosystem I. "
        "In photosystem II, light energy is used to split water molecules in a step called "
        "photolysis. Splitting water releases electrons, hydrogen ions and oxygen gas, so the "
        "oxygen released by plants comes from water, not from carbon dioxide. The energised "
        "electrons pass along an electron transport chain, and the energy they release pumps "
        "hydrogen ions into the thylakoid space. The ions flow back through the enzyme ATP "
        "synthase, which makes ATP. This is called chemiosmosis. At the end of the chain, "
        "photosystem I passes electrons to NADP+, forming NADPH. ATP and NADPH then power the "
        "Calvin cycle.",
    ),
    (
        "3. The Calvin cycle",
        "The Calvin cycle, also called the light-independent reactions, takes place in the "
        "stroma, the fluid that surrounds the thylakoids. It has three phases: carbon "
        "fixation, reduction and regeneration. In carbon fixation the enzyme RuBisCO attaches "
        "one molecule of carbon dioxide to a five-carbon sugar called RuBP. The unstable "
        "six-carbon product immediately splits into two molecules of 3-PGA. In the reduction "
        "phase, ATP and NADPH from the light-dependent reactions convert 3-PGA into G3P, a "
        "three-carbon sugar. In the regeneration phase most of the G3P is used, with more "
        "ATP, to rebuild RuBP so the cycle can continue. Making one G3P molecule that leaves "
        "the cycle requires three turns, fixing three carbon dioxide molecules and using nine "
        "ATP and six NADPH. Two G3P molecules can be combined to form one glucose.",
    ),
    (
        "4. Factors that limit photosynthesis",
        "The rate of photosynthesis depends on light intensity, carbon dioxide concentration "
        "and temperature. The factor in shortest supply is called the limiting factor, "
        "because raising any other factor will not increase the rate. Increasing light "
        "intensity raises the rate until it levels off at the light saturation point. "
        "Temperature matters because the Calvin cycle is driven by enzymes; above roughly 40 "
        "degrees Celsius these enzymes begin to denature and the rate falls sharply. In hot, "
        "dry conditions stomata close to save water, carbon dioxide runs low and RuBisCO "
        "starts binding oxygen instead, a wasteful process called photorespiration. C4 plants "
        "such as maize reduce photorespiration by first fixing carbon dioxide into a "
        "four-carbon compound. CAM plants such as cacti open their stomata only at night, "
        "storing carbon dioxide as an acid and so reducing water loss during the day.",
    ),
    (
        "5. Aerobic cellular respiration",
        "Cellular respiration releases the energy stored in glucose and captures it as ATP. "
        "The overall equation is C6H12O6 + 6O2 -> 6CO2 + 6H2O + energy. It has three main "
        "stages. Glycolysis happens in the cytoplasm and does not need oxygen: one glucose is "
        "split into two pyruvate molecules, with a net gain of two ATP and two NADH. Pyruvate "
        "then enters the mitochondrion and is converted to acetyl-CoA. The Krebs cycle, in "
        "the mitochondrial matrix, produces two ATP, six NADH, two FADH2 and four carbon "
        "dioxide molecules per glucose. Finally, the electron transport chain on the inner "
        "mitochondrial membrane uses NADH and FADH2 to make most of the ATP by oxidative "
        "phosphorylation, with oxygen as the final electron acceptor, forming water. In total "
        "one glucose yields about 30 to 32 ATP.",
    ),
    (
        "6. Fermentation and how the two processes connect",
        "When oxygen is not available, cells can keep making a little ATP through "
        "fermentation. Fermentation follows glycolysis and its main purpose is to regenerate "
        "NAD+ so that glycolysis can continue. It yields only the two ATP made in glycolysis, "
        "which is why it is far less efficient than aerobic respiration. In lactic acid "
        "fermentation, which happens in human muscle cells during intense exercise, pyruvate "
        "is converted into lactate. In alcoholic fermentation, carried out by yeast, pyruvate "
        "is converted into ethanol and carbon dioxide; this is used in brewing and in making "
        "bread rise. Photosynthesis and respiration are complementary: the glucose and oxygen "
        "produced by photosynthesis are the reactants of respiration, and the carbon dioxide "
        "and water released by respiration are the reactants of photosynthesis.",
    ),
]


def build_fixture_pdf() -> bytes:
    doc = pymupdf.open()
    for title, body in PAGES:
        page = doc.new_page(width=595, height=842)
        page.insert_text((56, 72), title, fontsize=16)
        leftover = page.insert_textbox(pymupdf.Rect(56, 96, 539, 786), body, fontsize=11)
        if leftover < 0:
            raise ValueError(f"Text does not fit on the page: {title}")
    data = doc.tobytes()
    doc.close()
    return data


def ensure_fixture_pdf() -> Path:
    if not FIXTURE_PDF.exists():
        FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
        FIXTURE_PDF.write_bytes(build_fixture_pdf())
    return FIXTURE_PDF


if __name__ == "__main__":
    print(f"Fixture ready at {ensure_fixture_pdf()}")
