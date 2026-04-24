#!/usr/bin/env python3
"""
fca_to_tikz.py

Reads all CSV files from a data/ directory (no headers, col1=object, col2=attribute),
computes FCA lattices, and writes one tikzpicture per file into fca.tex.

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
    objects = list(dict.fromkeys(o for o, _ in pairs))      # preserve order, unique
    attributes = list(dict.fromkeys(a for _, a in pairs))   # preserve order, unique

    # Build incidence table
    incidence = defaultdict(set)
    for obj, attr in pairs:
        incidence[obj].add(attr)

    # concepts expects a list of lists of booleans
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

    # BFS from infimum upward
    # Find infimum (concept with empty extent or fewest objects)
    infimum = min(concepts_list, key=lambda c: len(c.extent))
    layer[infimum] = 0

    # Topological pass using upper_neighbors
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

    # Fill any remaining (shouldn't happen in a connected lattice)
    for c in concepts_list:
        if c not in layer:
            layer[c] = 0

    return layer


def compute_positions(lattice, x_sep=2.5, y_sep=2.0):
    """
    Assign (x, y) positions to each concept.
    Layers by extent size (longest path from bottom).
    Within each layer, spread evenly.
    Returns dict: concept -> (x, y).
    """
    layer = assign_layers(lattice)
    max_layer = max(layer.values()) if layer else 0

    # Group concepts by layer
    by_layer = defaultdict(list)
    for c, l in layer.items():
        by_layer[l].append(c)

    positions = {}
    for l, group in by_layer.items():
        n = len(group)
        # Centre the group horizontally
        xs = [(i - (n - 1) / 2) * x_sep for i in range(n)]
        y = l * y_sep
        for c, x in zip(group, xs):
            positions[c] = (x, y)

    return positions


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


def concept_node_label(concept):
    """
    Build the TikZ node label for a concept.
    Objects (extent) go above the node, attributes (intent) go below.
    Only show objects/attributes that are 'new' at this concept
    (i.e., first introduced here), following standard FCA diagram convention.
    """
    # For simplicity (and robustness with the concepts library),
    # show all extent objects and intent attributes directly.
    # In a full implementation you would compute reduced labels;
    # here we show the full sets, which is correct for small lattices.
    objects = list(concept.extent)
    attrs = list(concept.intent)
    return objects, attrs


# ── TikZ generation ──────────────────────────────────────────────────────────

TIKZ_PREAMBLE = r"""\begin{tikzpicture}[
    concept/.style={circle, draw, fill=white, inner sep=2pt, minimum size=6pt},
    lbl/.style={font=\small},
    obj/.style={font=\small\itshape, text=blue!70!black},
    attr/.style={font=\small, text=red!70!black}
]
"""

TIKZ_POSTAMBLE = r"""\end{tikzpicture}"""


def lattice_to_tikz(lattice, title):
    """Return a full tikzpicture string for the given lattice."""
    positions = compute_positions(lattice)
    concepts_list = list(lattice)

    # Assign node IDs
    node_id = {c: f"n{i}" for i, c in enumerate(concepts_list)}

    lines = [TIKZ_PREAMBLE]

    # ── draw edges first (so nodes appear on top) ──
    lines.append("  % Hasse edges\n")
    for c in concepts_list:
        for upper in c.upper_neighbors:
            x1, y1 = positions[c]
            x2, y2 = positions[upper]
            lines.append(
                f"  \\draw ({x1:.3f},{y1:.3f}) -- ({x2:.3f},{y2:.3f});\n"
            )

    # ── draw nodes ──
    lines.append("  % Concept nodes\n")
    for c in concepts_list:
        x, y = positions[c]
        nid = node_id[c]
        lines.append(
            f"  \\node[concept] ({nid}) at ({x:.3f},{y:.3f}) {{}};\n"
        )

    # ── object labels (above each node) ──
    lines.append("  % Object labels (above)\n")
    for c in concepts_list:
        x, y = positions[c]
        objects, _ = concept_node_label(c)
        if objects:
            label = r" \\ ".join(tikz_safe(o) for o in objects)
            lines.append(
                f"  \\node[obj, above=2pt of {node_id[c]}, align=center]"
                f" {{\\begin{{tabular}}{{c}}{label}\\end{{tabular}}}};\n"
            )

    # ── attribute labels (below each node) ──
    lines.append("  % Attribute labels (below)\n")
    for c in concepts_list:
        x, y = positions[c]
        _, attrs = concept_node_label(c)
        if attrs:
            label = r" \\ ".join(tikz_safe(a) for a in attrs)
            lines.append(
                f"  \\node[attr, below=2pt of {node_id[c]}, align=center]"
                f" {{\\begin{{tabular}}{{c}}{label}\\end{{tabular}}}};\n"
            )

    lines.append(TIKZ_POSTAMBLE)
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
    doc_lines.append("% Requires: tikz, positioning libraries\n")
    doc_lines.append("% Add to preamble: \\usepackage{tikz}\n")
    doc_lines.append("%                  \\usetikzlibrary{positioning}\n\n")

    for fname in csv_files:
        title = os.path.splitext(fname)[0].replace("_", " ")
        fpath = os.path.join(data_dir, fname)
        print(f"Processing {fname} ...")

        pairs = load_csv(fpath)
        if not pairs:
            print(f"  Skipping {fname}: no valid data.")
            continue

        ctx, objects, attributes = build_context(pairs)
        print(f"  Objects: {len(objects)}, Attributes: {len(attributes)}, "
              f"Concepts: {len(list(ctx.lattice))}")

        tikz = lattice_to_tikz(ctx.lattice, title)

        doc_lines.append(f"% {'─' * 60}\n")
        doc_lines.append(f"% {title}\n")
        doc_lines.append(f"% {'─' * 60}\n")
        doc_lines.append("\\begin{figure}[htbp]\n")
        doc_lines.append("  \\centering\n")
        doc_lines.append(f"  {tikz}\n")
        doc_lines.append(
            f"  \\caption{{FCA lattice: {tikz_safe(title)}}}\n"
        )
        doc_lines.append(
            f"  \\label{{fig:fca-{os.path.splitext(fname)[0]}}}\n"
        )
        doc_lines.append("\\end{figure}\n\n")

    with open(output_path, "w", encoding="utf-8") as f:
        f.writelines(doc_lines)

    print(f"\nWritten to {output_path}")


if __name__ == "__main__":
    main()