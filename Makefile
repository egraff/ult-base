NAME = ult-base

# Try to locate user's local texmf tree
ULTTEXMFHOME = $(shell kpsewhich --var-value TEXMFHOME)
ULTTEXMFLOCAL = $(shell kpsewhich --var-value TEXMFLOCAL)

all: help

help:
	@echo "ult-base makefile targets:"
	@echo " "
	@echo "          help  -  (this message)"
	@echo " "
	@echo "       install  -  install the ult-base packages into your home texmf tree"
	@echo "     uninstall  -  remove the ult-base packages from your home texmf tree"

define prompt-texmf
	@while [ -z "$$CONTINUE" ]; do                                          \
	    read -r -p "Is this correct? [y/N] " CONTINUE;                      \
	done ;                                                                  \
	if [ $$CONTINUE != "y" ] && [ $$CONTINUE != "Y" ]; then                 \
	    echo "Exiting." ; exit 1 ;                                          \
	fi
endef


# If ULTTEXMFLOCAL is on the kpathsea form {dir1:dir2:dir3} or {dir1;dir2;dir3} or {dir1,dir2,dir3},
# then select the first directory from the list. Otherwise, use ULTTEXMFLOCAL verbatim.
define parse-ulttexmflocal
	MULTI_PATHS=$$(echo "$(ULTTEXMFLOCAL)" | sed -n 's/^{\(.*\)}/\1/p') ;   \
	if [ ! -z "$$MULTI_PATHS" ]; then                                       \
	    if [ "$(OS)" = "Windows_NT" ]; then                                 \
	        IFS=';,' ;                                                      \
	    else                                                                \
	        IFS=';:,' ;                                                     \
	    fi ;                                                                \
	    for p in $$MULTI_PATHS; do                                          \
	        echo "$$p" ;                                                    \
	        break ;                                                         \
	    done ;                                                              \
	else                                                                    \
	    echo "$(ULTTEXMFLOCAL)" ;                                           \
	fi
endef


# TEXMFHOME is prioritized. ULTTEXMFLOCAL is initially set to TEXMFLOCAL, but
# if TEXMFHOME is defined, it will override ULTTEXMFLOCAL
try-texmf-home:
ifneq ($(ULTTEXMFHOME),)
  ULTTEXMFLOCAL = $(ULTTEXMFHOME)
endif

# If either TEXMFHOME or TEXMFLOCAL is defined, try to parse it
try-texmf-local: try-texmf-home
ifneq ($(ULTTEXMFLOCAL),)
  ULTPARSEDTEXMF = $(shell $(parse-ulttexmflocal))
endif

# If neither TEXMFHOME nor TEXMFLOCAL is defined
check-ulttexmf: try-texmf-local
ifeq ($(ULTPARSEDTEXMF),)
	@echo "Cannot locate your home texmf tree. Specify manually with"
	@echo " "
	@echo "    make install TEXMF=/path/to/texmf"
	@echo " "
	@exit 1
else
  TEXMF = $(ULTPARSEDTEXMF)
endif


ifdef TEXMF
detect-texmf:
else
detect-texmf: check-ulttexmf
endif
	@echo "Using texmf tree in \"$(TEXMF)\"."
	$(prompt-texmf)
ULTTEXMF = $(subst \,/,$(TEXMF))
LATEXROOT = $(ULTTEXMF)/tex/latex/$(NAME)
LOCALLATEXROOT = texmf-tds/tex/latex/$(NAME)

check-texmf: detect-texmf
	@test -d "$(ULTTEXMF)" || mkdir -p "$(ULTTEXMF)"

uninstall: check-texmf
	@echo "$(ULTTEXMF)/tex/latex/$(NAME)"
	@if [ -d "$(LATEXROOT)" ]; then \
	    echo "Uninstalling..." ; \
	    rm -rf "$(LATEXROOT)" ; \
	    echo "Uninstalled." ; \
	    echo "You might have to run 'texhash' to update your texmf database." ; \
	fi

install: check-texmf uninstall
	@echo "Installing into \"$(LATEXROOT)\"..."
	@test -d "$(LATEXROOT)" || mkdir -p "$(LATEXROOT)"
	@cp -r -v "$(LOCALLATEXROOT)"/* "$(LATEXROOT)/"
	@if [ $$? -ne 0 ]; then \
	    echo "Failed to copy class files to texmf directory" ; \
	    exit 1 ; \
	fi
	@git rev-parse --verify HEAD > "$(LATEXROOT)/REVISION"
	@echo "Done."
	@echo "You might have to run 'texhash' to update your texmf database." ; \
