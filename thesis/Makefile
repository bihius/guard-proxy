# =============================================================================
# DSW Thesis Build Pipeline
# =============================================================================
# Markdown -> Pandoc -> XeLaTeX -> PDF
#
# Usage:
#   make          - Build the PDF
#   make clean    - Remove output files
#   make debug    - Generate intermediate .tex file for inspection
#   make watch    - Auto-rebuild on file changes (requires fswatch)
#   make wordcount - Count words in chapters
#   make check    - Validate bibliography and CSL
# =============================================================================

# --- Configuration ---
PANDOC     := pandoc
SHELL      := /bin/bash
CHAPTERS   := $(sort $(wildcard chapters/*.md))
OUTPUT_DIR := output
OUTPUT_PDF := $(OUTPUT_DIR)/praca_inz.pdf
OUTPUT_TEX := $(OUTPUT_DIR)/praca_inz.tex
METADATA   := metadata.yaml
TEMPLATE   := templates/dsw-thesis.latex
TITLEPAGE  := templates/titlepage.latex
CSL        := csl/dsw-footnote.csl
BIB        := bibliography/references.bib

# --- Pandoc Common Flags ---
PANDOC_FLAGS := \
	--metadata-file=$(METADATA) \
	--template=$(TEMPLATE) \
	--csl=$(CSL) \
	--bibliography=$(BIB) \
	--pdf-engine=xelatex \
	--citeproc \
	--number-sections \
	--resource-path=.:assets

# Ensure PATH includes TeX binaries
export PATH := /Library/TeX/texbin:$(PATH)

# =============================================================================
# TARGETS
# =============================================================================

.PHONY: all clean debug watch wordcount check help

## Build the PDF thesis
all: $(OUTPUT_PDF)

$(OUTPUT_PDF): $(CHAPTERS) $(METADATA) $(TEMPLATE) $(TITLEPAGE) $(CSL) $(BIB) | $(OUTPUT_DIR)
	@echo "Building PDF..."
	$(PANDOC) $(PANDOC_FLAGS) \
		-o $@ \
		$(CHAPTERS)
	@echo "Done: $@"

## Create output directory
$(OUTPUT_DIR):
	mkdir -p $(OUTPUT_DIR)

## Generate intermediate .tex for debugging
debug: $(CHAPTERS) $(METADATA) $(TEMPLATE) $(TITLEPAGE) $(CSL) $(BIB) | $(OUTPUT_DIR)
	@echo "Generating .tex file..."
	$(PANDOC) $(PANDOC_FLAGS) \
		-s \
		-o $(OUTPUT_TEX) \
		$(CHAPTERS)
	@echo "Done: $(OUTPUT_TEX)"

## Remove all generated files
clean:
	@echo "Cleaning output..."
	rm -rf $(OUTPUT_DIR)/*.pdf $(OUTPUT_DIR)/*.tex $(OUTPUT_DIR)/*.log
	@echo "Done."

## Auto-rebuild on file changes (requires: brew install fswatch)
watch:
	@echo "Watching for changes... (Ctrl+C to stop)"
	@fswatch -o chapters/ templates/ bibliography/ csl/ metadata.yaml \
		| xargs -n1 -I{} $(MAKE) all

## Count words in all chapters (approximate)
wordcount:
	@echo "Word count per chapter:"
	@for f in $(CHAPTERS); do \
		words=$$(cat "$$f" | sed '/^<!--/,/-->/d' | wc -w | tr -d ' '); \
		echo "  $$f: $$words words"; \
	done
	@echo "---"
	@total=$$(cat $(CHAPTERS) | sed '/^<!--/,/-->/d' | wc -w | tr -d ' '); \
	echo "  TOTAL: $$total words"

## Validate that pandoc can parse the files
check:
	@echo "Checking pandoc can parse all chapters..."
	@$(PANDOC) --metadata-file=$(METADATA) --csl=$(CSL) --bibliography=$(BIB) \
		--citeproc -t plain $(CHAPTERS) > /dev/null 2>&1 \
		&& echo "OK: All chapters parse successfully." \
		|| echo "ERROR: Parsing failed. Run 'make debug' to inspect."

## Show available targets
help:
	@echo "DSW Thesis Build System"
	@echo ""
	@echo "Targets:"
	@echo "  make          - Build the PDF (output/praca_inz.pdf)"
	@echo "  make clean    - Remove generated files"
	@echo "  make debug    - Generate .tex file for inspection"
	@echo "  make watch    - Auto-rebuild on changes (needs fswatch)"
	@echo "  make wordcount - Count words per chapter"
	@echo "  make check    - Validate that pandoc can parse the files"
	@echo "  make help     - Show this help message"
