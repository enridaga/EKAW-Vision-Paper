#!/usr/bin/env python3
"""
fca_to_tikz.py

Reads all CSV files from a data/ directory (no headers, col1=object, col2=attribute),
computes FCA lattices, and writes one tikzpicture per file into fca.tex.
Each concept node is labelled with an alphanumeric ID (a1, b1, ... for lattice 1,
a2, b2, ... for lattice 2, etc.). A legend longtable per lattice lists ID, Objects,
and Attributes for each concept, and may span multiple pages.

Requires in LaTeX preamble:
  \\usepackage{tikz}
  \\usetikzlibrary{positioning}
  \\usepackage{float}       % for [H] placement of figures
  \\usepackage{array}       % for p{} column type
  \\usepackage{longtable}   % for page-spanning legend tables

Usage: python3 fca_to_tikz.py [--data DIR] [--output FILE]
"""

import csv
import os
import argparse
from collections import defaultdict
import concepts


# ── helpers ──────────────────────────────────────────────────────────────────

def load_csv(path):
    """Return list of (object, attribute) pairs from a headerless CSV."""
    pairs = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                obj = row[0].strip()
                attr = row[1].strip()
                if obj and attr:
                    pairs.append((obj, attr))
    return pairs


def build_context(pairs):
    """
    Build a concepts.Context from (object, attribute) pairs.
    Returns (context, objects_list, attributes_list).
    """
    objects = list(dict.fromkeys(o for o, _ in pairs))
    attributes = list(dict.fromkeys(a for _, a in pairs))

    incidence = defaultdict(set)
    for obj, attr in pairs:
        incidence[obj].add(attr)

    table = [[attr in incidence[obj] for attr in attributes] for obj in objects]

    ctx = concepts.Context(objects, attributes, table)
    return ctx, objects, attributes


def assign_layers(lattice):
    """
    Assign a y-layer to each concept by longest path from infimum (bottom).
    Returns dict: concept -> layer (0 = bottom, max = top).
    """
    layer = {}
    concepts_list = list(lattice)

    infimum = min(concepts_list, key=lambda c: len(c.extent))
    layer[infimum] = 0

    changed = True
    while changed:
        changed = False
        for c in concepts_list:
            if c not in layer:
                continue
            for upper in c.upper_neighbors:
                new_layer = layer[c] + 1
                if upper not in layer or layer[upper] < new_layer:
                    layer[upper] = new_layer
                    changed = True

    for c in concepts_list:
        if c not in layer:
            layer[c] = 0

    return layer


def compute_positions(lattice, x_sep=2.5, y_sep=2.0):
    """
    Assign (x, y) positions to each concept.
    Within each layer, concepts are spread evenly and horizontally centred.
    Returns dict: concept -> (x, y).
    """
    layer = assign_layers(lattice)

    by_layer = defaultdict(list)
    for c, l in layer.items():
        by_layer[l].append(c)

    positions = {}
    for l, group in by_layer.items():
        n = len(group)
        xs = [(i - (n - 1) / 2) * x_sep for i in range(n)]
        y = l * y_sep
        for c, x in zip(group, xs):
            positions[c] = (x, y)

    return positions


def sorted_concepts(lattice, positions):
    """
    Return concepts sorted bottom-to-top, left-to-right:
    primary key = y position (ascending), secondary key = x position (ascending).
    This defines the order in which alphanumeric IDs are assigned.
    """
    return sorted(lattice, key=lambda c: (positions[c][1], positions[c][0]))


def generate_ids(n, lattice_index):
    """
    Generate n alphanumeric IDs for lattice number lattice_index (1-based).
    Sequence: a, b, ..., z, aa, ab, ..., az, ba, ...
    Each ID is suffixed with the lattice index, e.g. 'a1', 'b1', 'aa1'.
    """
    ids = []
    for i in range(n):
        label = ""
        j = i
        while True:
            label = chr(ord('a') + j % 26) + label
            j = j // 26 - 1
            if j < 0:
                break
        ids.append(f"{label}{lattice_index}")
    return ids


def tikz_safe(s):
    """Escape special LaTeX characters in labels."""
    return (s.replace('\\', '\\textbackslash{}')
             .replace('&', '\\&')
             .replace('%', '\\%')
             .replace('$', '\\$')
             .replace('#', '\\#')
             .replace('_', '\\_')
             .replace('{', '\\{')
             .replace('}', '\\}')
             .replace('~', '\\textasciitilde{}')
             .replace('^', '\\textasciicircum{}'))


# ── TikZ generation ──────────────────────────────────────────────────────────

TIKZ_PREAMBLE = r"""\begin{tikzpicture}[
    concept/.style={circle, draw, fill=white, inner sep=4pt, minimum size=16pt,
                    font=\small\bfseries},
    lbl/.style={font=\small}
]
"""

TIKZ_POSTAMBLE = r"""\end{tikzpicture}"""


def lattice_to_tikz(lattice, positions, concept_id):
    """
    Return a full tikzpicture string for the given lattice.
    concept_id: dict mapping concept -> alphanumeric ID string.
    """
    concepts_list = list(lattice)
    node_name = {c: f"n{i}" for i, c in enumerate(concepts_list)}

    #lines = [TIKZ_PREAMBLE]
    #lines = ["\\resizebox{\\textwidth}{!}{%\n", TIKZ_PREAMBLE]
    lines = ["\\adjustbox{max width=\\textwidth, max totalheight=\\textheight}{%\n", TIKZ_PREAMBLE]
    
    # ── edges first so nodes render on top ──
    lines.append("  % Hasse edges\n")
    for c in concepts_list:
        for upper in c.upper_neighbors:
            x1, y1 = positions[c]
            x2, y2 = positions[upper]
            lines.append(
                f"  \\draw ({x1:.3f},{y1:.3f}) -- ({x2:.3f},{y2:.3f});\n"
            )

    # ── nodes with ID label inside ──
    lines.append("  % Concept nodes\n")
    for c in concepts_list:
        x, y = positions[c]
        nname = node_name[c]
        cid = tikz_safe(f"({concept_id[c]})")
        lines.append(
            f"  \\node[concept] ({nname}) at ({x:.3f},{y:.3f}) {{{cid}}};\n"
        )

    lines.append(TIKZ_POSTAMBLE)
    lines.append("\n}%\n")
    return "".join(lines)


# ── Legend table generation ───────────────────────────────────────────────────

def lattice_to_legend_table(lattice, concept_id, title, fname_base):
    """
    Return a LaTeX longtable with three columns: ID, Objects, Attributes.
    - longtable flows in the document without floating, spans pages naturally.
    - Caption appears at the top and cross-references the lattice figure.
    - Column headers repeat on each page.
    - Objects and Attributes columns use p{6cm} to wrap long content.
    """
    ordered = sorted(concept_id.keys(), key=lambda c: concept_id[c])

    caption_text = (
        f"Concept legend for the FCA lattice in "
        f"Figure~\\ref{{fig:fca-{fname_base}}}: {tikz_safe(title)}"
    )
    continued_caption = (
        f"Concept legend for the FCA lattice in "
        f"Figure~\\ref{{fig:fca-{fname_base}}}: {tikz_safe(title)} (continued)"
    )

    lines = []
    lines.append("\\small\n")
    lines.append("\\begin{longtable}{l p{6cm} p{6cm}}\n")

    # ── caption and label (top, before first header) ──
    lines.append(f"  \\caption{{{caption_text}}} \\\\\n")
    lines.append(f"  \\label{{tab:fca-{fname_base}}} \\\\\n")

    # ── first-page header ──
    lines.append("  \\hline\n")
    lines.append(
        "  \\textbf{ID} & \\textbf{Objects} & \\textbf{Attributes} \\\\\n"
    )
    lines.append("  \\hline\n")
    lines.append("  \\endfirsthead\n")

    # ── continuation header (repeated on subsequent pages) ──
    lines.append(f"  \\multicolumn{{3}}{{l}}{{\\small\\itshape {continued_caption}}} \\\\\n")
    lines.append("  \\hline\n")
    lines.append(
        "  \\textbf{ID} & \\textbf{Objects} & \\textbf{Attributes} \\\\\n"
    )
    lines.append("  \\hline\n")
    lines.append("  \\endhead\n")

    # ── footer on all pages except last ──
    lines.append("  \\hline\n")
    lines.append(
        "  \\multicolumn{3}{r}{\\small\\itshape Continued on next page} \\\\\n"
    )
    lines.append("  \\endfoot\n")

    # ── final footer ──
    lines.append("  \\hline\n")
    lines.append("  \\endlastfoot\n")

    # ── data rows ──
    for c in ordered:
        cid = tikz_safe(f"({concept_id[c]})")
        objects_str = tikz_safe(", ".join(c.extent)) if c.extent else "---"
        attrs_str = tikz_safe(", ".join(c.intent)) if c.intent else "---"
        lines.append(
            f"  {cid} & {objects_str} & {attrs_str} \\\\\n"
        )

    lines.append("\\end{longtable}\n")
    lines.append("\\normalsize\n")

    return "".join(lines)


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Generate FCA TikZ lattices from CSV files.")
    parser.add_argument("--data", default="data", help="Directory containing CSV files")
    parser.add_argument("--output", default="fca.tex", help="Output LaTeX file")
    args = parser.parse_args()

    data_dir = args.data
    output_path = args.output

    csv_files = sorted(
        f for f in os.listdir(data_dir) if f.lower().endswith(".csv")
    )

    if not csv_files:
        print(f"No CSV files found in {data_dir}/")
        return

    doc_lines = []
    doc_lines.append("% Auto-generated FCA lattices\n")
    doc_lines.append("% Requires in LaTeX preamble:\n")
    doc_lines.append("%   \\usepackage{tikz}\n")
    doc_lines.append("%   \\usetikzlibrary{positioning}\n")
    doc_lines.append("%   \\usepackage{float}       % for [H] placement of figures\n")
    doc_lines.append("%   \\usepackage{array}       % for p{} column type\n")
    doc_lines.append("%   \\usepackage{longtable}   % for page-spanning legend tables\n\n")
    doc_lines.append("%   \\usepackage{adjustbox}   % for max width+height scaling of figures\n")

    for lattice_index, fname in enumerate(csv_files, start=1):
        title = os.path.splitext(fname)[0].replace("_", " ")
        fname_base = os.path.splitext(fname)[0]
        fpath = os.path.join(data_dir, fname)
        print(f"Processing {fname} (lattice {lattice_index}) ...")

        pairs = load_csv(fpath)
        if not pairs:
            print(f"  Skipping {fname}: no valid data.")
            continue

        ctx, objects, attributes = build_context(pairs)
        lattice = ctx.lattice
        n_concepts = len(list(lattice))
        print(f"  Objects: {len(objects)}, Attributes: {len(attributes)}, "
              f"Concepts: {n_concepts}")

        # Compute positions and assign ordered IDs
        positions = compute_positions(lattice)
        ordered = sorted_concepts(lattice, positions)
        ids = generate_ids(n_concepts, lattice_index)
        concept_id = {c: ids[i] for i, c in enumerate(ordered)}

        # Figure
        tikz = lattice_to_tikz(lattice, positions, concept_id)

        doc_lines.append(f"% {'─' * 60}\n")
        doc_lines.append(f"% {title}\n")
        doc_lines.append(f"% {'─' * 60}\n")
        doc_lines.append("\\begin{figure}[H]\n")
        doc_lines.append("  \\centering\n")
        doc_lines.append(f"  {tikz}\n")
        doc_lines.append(
            f"  \\caption{{FCA lattice: {tikz_safe(title)}. "
            f"See Table~\\ref{{tab:fca-{fname_base}}} for concept legend.}}\n"
        )
        doc_lines.append(
            f"  \\label{{fig:fca-{fname_base}}}\n"
        )
        doc_lines.append("\\end{figure}\n\n")

        # Legend longtable immediately after
        table = lattice_to_legend_table(lattice, concept_id, title, fname_base)
        doc_lines.append(table)
        doc_lines.append("\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(doc_lines)

    print(f"\nWritten to {output_path}")


if __name__ == "__main__":
    main()