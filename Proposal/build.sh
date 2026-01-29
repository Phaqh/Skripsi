#!/usr/bin/env bash
# 
# created by: Muhammad Rifqi Fatchurrahman Putra Danar
#


echo PDF-ing
pdflatex -shell-escape -interaction=nonstopmode index.tex
pdflatex -shell-escape -interaction=nonstopmode index.tex
bibtex index.aux
pdflatex -interaction=nonstopmode index.tex
echo DONE
