import csv
from collections import defaultdict

def load_csv(filepath):
    """Load a CSV file with KG,keyword pairs."""
    data = defaultdict(set)
    keywords = set()
    with open(filepath, newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) == 2:
                kg, keyword = row[0].strip(), row[1].strip()
                data[kg].add(keyword)
                keywords.add(keyword)
    return data, keywords

def get_ordered_kgs(filepaths):
    """Get ordered list of KGs preserving order of first appearance."""
    kgs = []
    for filepath in filepaths:
        with open(filepath, newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) == 2:
                    kg = row[0].strip()
                    if kg not in kgs:
                        kgs.append(kg)
    return kgs

def build_ordered_keywords(data, keywords, kgs):
    """Order keywords from most to least popular across KGs."""
    keyword_counts = {kw: sum(1 for kg in kgs if kw in data[kg]) for kw in keywords}
    ordered_keywords = sorted(keywords, key=lambda kw: keyword_counts[kw], reverse=True)
    return ordered_keywords

def generate_latex_table(data, ordered_keywords, kgs, caption, label):
    """Generate a LaTeX table from the binary matrix."""
    num_cols = len(kgs)
    col_spec = 'l' + 'c' * num_cols

    lines = []
    lines.append(r'\begin{table}[ht]')
    lines.append(r'\centering')
    lines.append(r'\small')
    lines.append(r'\begin{tabular}{' + col_spec + r'}')
    lines.append(r'\toprule')

    # Header row
    header = ' & ' + ' & '.join([r'\rotatebox{90}{\textbf{' + kg + '}}' for kg in kgs])
    lines.append(header + r' \\')
    lines.append(r'\midrule')

    # Data rows
    for kw in ordered_keywords:
        row = r'\textit{' + kw + '}'
        for kg in kgs:
            if kw in data[kg]:
                row += r' & $\times$'
            else:
                row += ' & '
        row += r' \\'
        lines.append(row)

    lines.append(r'\bottomrule')
    lines.append(r'\end{tabular}')
    lines.append(r'\caption{' + caption + '}')
    lines.append(r'\label{' + label + '}')
    lines.append(r'\end{table}')

    return '\n'.join(lines)

def main():
    # File paths
    files = {
        'sem_props':    'data/semantic_properties.csv',
        'sem_affords':  'data/semantic_affordances.csv',
        'prag_props':   'data/pragmatic_properties.csv',
        'prag_affords': 'data/pragmatic_affordances.csv',
    }

    # Load all data
    sem_props_data,   sem_props_kws   = load_csv(files['sem_props'])
    sem_affords_data, sem_affords_kws = load_csv(files['sem_affords'])
    prag_props_data,  prag_props_kws  = load_csv(files['prag_props'])
    prag_affords_data,prag_affords_kws= load_csv(files['prag_affords'])

    # Get ordered KGs from all files
    kgs = get_ordered_kgs(list(files.values()))

    # Build ordered keywords for each dimension
    ordered_sem_props   = build_ordered_keywords(sem_props_data,   sem_props_kws,   kgs)
    ordered_sem_affords = build_ordered_keywords(sem_affords_data, sem_affords_kws, kgs)
    ordered_prag_props  = build_ordered_keywords(prag_props_data,  prag_props_kws,  kgs)
    ordered_prag_affords= build_ordered_keywords(prag_affords_data,prag_affords_kws,kgs)

    # Generate LaTeX tables
    tables = [
        (sem_props_data,    ordered_sem_props,
         'Semantic properties of provenance across knowledge graphs.',
         'tab:semantic_properties'),
        (sem_affords_data,  ordered_sem_affords,
         'Semantic affordances of provenance across knowledge graphs.',
         'tab:semantic_affordances'),
        (prag_props_data,   ordered_prag_props,
         'Pragmatic properties of provenance across knowledge graphs.',
         'tab:pragmatic_properties'),
        (prag_affords_data, ordered_prag_affords,
         'Pragmatic affordances of provenance across knowledge graphs.',
         'tab:pragmatic_affordances'),
    ]

    # Write output
    with open('tables.tex', 'w', encoding='utf-8') as f:
        for data, ordered_kws, caption, label in tables:
            f.write(f'% {caption}\n')
            f.write(generate_latex_table(data, ordered_kws, kgs, caption, label))
            f.write('\n\n')

    print('Tables written to tables.tex')

if __name__ == '__main__':
    main()