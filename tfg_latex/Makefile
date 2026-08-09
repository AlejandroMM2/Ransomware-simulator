# Makefile para el TFG — UNED ETSI Informática
MAIN = main
LATEX = pdflatex
BIBTEX = bibtex
GLOSSARIES = makeglossaries
LATEXFLAGS = -interaction=nonstopmode

.PHONY: all clean

all: $(MAIN).pdf

$(MAIN).pdf: $(MAIN).tex
	@echo "==> Pasada 1: pdflatex"
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	@echo "==> Bibliografía: bibtex"
	$(BIBTEX) $(MAIN)
	@echo "==> Glosario: makeglossaries"
	$(GLOSSARIES) $(MAIN)
	@echo "==> Pasada 2: pdflatex"
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	@echo "==> Pasada 3: pdflatex (referencias cruzadas)"
	$(LATEX) $(LATEXFLAGS) $(MAIN)
	@echo "==> PDF generado: $(MAIN).pdf"

clean:
	@echo "==> Limpiando ficheros temporales"
	rm -f $(MAIN).{aux,bbl,bcf,blg,glg,glo,gls,idx,ilg,ind,\
	          lof,log,lot,out,run.xml,toc,xdy,acn,acr,alg,ist}
	rm -f capitulos/*.aux
	@echo "==> Limpieza completada"
