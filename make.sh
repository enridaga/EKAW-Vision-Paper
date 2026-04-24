#!/bin/bash

python3 bin/fca_to_tikz.py --data data/ --output fca.tex && python bin/make-tables.py && pdflatex main && bibtex main && pdflatex main && pdflatex main

