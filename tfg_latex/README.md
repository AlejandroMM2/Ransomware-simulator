# Memoria TFG — LaTeX

## Estructura de ficheros

```
tfg_latex/
├── main.tex                    # Documento principal (portada, preliminares, cuerpo, anexos)
├── acronimos.tex               # Definiciones de acrónimos (glossaries), en español
├── bibliografia.bib            # Bibliografía (BibTeX, estilo IEEEtran)
├── Makefile                    # Automatización de compilación (pdflatex + bibtex + makeglossaries)
├── capitulos/
│   ├── agradecimientos.tex
│   ├── resumen.tex
│   ├── abstract.tex
│   ├── C1-introduccion.tex
│   ├── C2-estado_arte.tex
│   ├── C3-arquitectura.tex
│   ├── C4-disenyo_experimental.tex
│   ├── C5-resultados.tex
│   ├── C6-discusion.tex
│   ├── C7-conclusiones.tex
│   ├── referencias.tex         # \bibliography{../bibliografia}
│   ├── A1-reglas_wazuh.tex
│   ├── A2-atomic_red_team.tex
│   └── A3-repositorio.tex
├── imagenes/                   # Figuras e imagen de portada
└── _obsoletos/                 # Ficheros huérfanos de una versión anterior del proyecto,
                                 # no referenciados por main.tex (se conservan por si acaso;
                                 # pueden borrarse sin afectar a la compilación)
```

## Compilar el PDF

### Opción 1: con Make (recomendado)
```bash
make
```
Ejecuta la secuencia completa: pdflatex → bibtex → makeglossaries → pdflatex × 2.

### Opción 2: manual
```bash
pdflatex main
bibtex main
makeglossaries main
pdflatex main
pdflatex main
```

### Opción 3: compilación rápida (sin bibliografía ni glosario)
```bash
make fast
```

## Dependencias LaTeX

Paquetes necesarios (incluidos en TeX Live full):
- `babel` (spanish)
- `bibtex` + estilo `IEEEtran.bst` (paquete `ieeetran` en TeX Live)
- `booktabs`, `tabularx`, `colortbl`, `siunitx`
- `listings`, `lstautogobble`
- `hyperref`
- `glossaries`
- `xcolor`
- `geometry`
- `fancyhdr`
- `subfiles`

### Instalar en Ubuntu/Debian:
```bash
sudo apt-get install texlive-full
```

### Instalar en Arch/CachyOS:
```bash
sudo pacman -S texlive-most
```

## Notas de la última revisión

- Se corrigió el uso de `biber` en el Makefile: el documento usa `\bibliography` +
  `\bibliographystyle{IEEEtran}` (BibTeX clásico), no `biblatex`, por lo que la
  bibliografía se genera con `bibtex`, no con `biber`.
- Se corrigió la ruta de `\bibliography{../bibliografia}` en `capitulos/referencias.tex`:
  el paquete `subfiles` resuelve las rutas relativas respecto al directorio del
  subfichero (`capitulos/`), por lo que la referencia debía subir un nivel.
  Esta era la causa de las citas sin resolver (`Wazuh [?]`, `MinIO [?]`, etc.).
- Se tradujeron al español las entradas de `acronimos.tex` y los títulos cortos
  de `\caption[...]` de tablas y figuras (antes en inglés, aunque el cuerpo del
  documento está en español).
- Se unificó la fecha de portada/hoja de datos (`\PFGconvocatoria` /
  `\PFGfechadefensa` en `main.tex`).
- Se sustituyeron los `\textcite{...}` (comando de `biblatex`) por
  `Autor \cite{...}` (compatible con el `\cite` de BibTeX clásico usado en el
  resto del documento) en `C2-estado_arte.tex` y `C6-discusion.tex`.
- Se amplió el contenido de los capítulos 1, 2, 4 y 6 (introducción, estado del
  arte, diseño experimental y discusión) para aumentar la extensión del
  documento.
