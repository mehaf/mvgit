MAN1_TXT= \
	$(filter-out $(addsuffix .txt, $(ARTICLES) $(SP_ARTICLES)), \
		$(wildcard git-*.txt))

MAN_TXT = $(MAN1_TXT)
MAN_XML=$(patsubst %.txt,%.xml,$(MAN_TXT))
MAN_HTML=$(patsubst %.txt,%.html,$(MAN_TXT))

DOC_HTML=$(MAN_HTML)

ARTICLES = 
# with their own formatting rules.
SP_ARTICLES =
API_DOCS =
SP_ARTICLES +=
SP_ARTICLES +=

DOC_HTML += $(patsubst %,%.html,$(ARTICLES) $(SP_ARTICLES))

DOC_MAN1=$(patsubst %.txt,%.1,$(MAN1_TXT))

prefix?=$(HOME)
bindir?=$(prefix)/bin
mandir?=$(prefix)/share/man
htmldir?=$(prefix)/share/doc/git-doc
man1dir=$(mandir)/man1
# DESTDIR=

ASCIIDOC=asciidoc
ASCIIDOC_EXTRA =
MANPAGE_XSL = manpage-normal.xsl
XMLTO_EXTRA =
INSTALL?=install
RM ?= rm -f
DOC_REF = origin/man
HTML_REF = origin/html

DOCBOOK2X_TEXI=docbook2x-texi
DBLATEX=dblatex
ifndef PERL_PATH
	PERL_PATH = /usr/bin/perl
endif

#
# For asciidoc ...
#	-7.1.2,	no extra settings are needed.
#	8.0-,	set ASCIIDOC8.
#

#
# For docbook-xsl ...
#	-1.68.1,	set ASCIIDOC_NO_ROFF? (based on changelog from 1.73.0)
#	1.69.0,		no extra settings are needed?
#	1.69.1-1.71.0,	set DOCBOOK_SUPPRESS_SP?
#	1.71.1,		no extra settings are needed?
#	1.72.0,		set DOCBOOK_XSL_172.
#	1.73.0-,	set ASCIIDOC_NO_ROFF
#

#
# If you had been using DOCBOOK_XSL_172 in an attempt to get rid
# of 'the ".ft C" problem' in your generated manpages, and you
# instead ended up with weird characters around callouts, try
# using ASCIIDOC_NO_ROFF instead (it works fine with ASCIIDOC8).
#

ifdef ASCIIDOC8
ASCIIDOC_EXTRA += -a asciidoc7compatible
endif
ifdef DOCBOOK_XSL_172
ASCIIDOC_EXTRA += -a mvgit-asciidoc-no-roff
MANPAGE_XSL = manpage-1.72.xsl
else
	ifdef ASCIIDOC_NO_ROFF
	# docbook-xsl after 1.72 needs the regular XSL, but will not
	# pass-thru raw roff codes from asciidoc.conf, so turn them off.
	ASCIIDOC_EXTRA += -a mvgit-asciidoc-no-roff
	endif
endif
ifdef MAN_BOLD_LITERAL
XMLTO_EXTRA += -m manpage-bold-literal.xsl
endif
ifdef DOCBOOK_SUPPRESS_SP
XMLTO_EXTRA += -m manpage-suppress-sp.xsl
endif

SHELL_PATH ?= $(SHELL)
# Shell quote;
SHELL_PATH_SQ = $(subst ','\'',$(SHELL_PATH))

#
# Please note that there is a minor bug in asciidoc.
# The version after 6.0.3 _will_ include the patch found here:
#   http://marc.theaimsgroup.com/?l=git&m=111558757202243&w=2
#
# Until that version is released you may have to apply the patch
# yourself - yes, all 6 characters of it!
#

QUIET_SUBDIR0  = +$(MAKE) -C # space to separate -C and subdir
QUIET_SUBDIR1  =

ifneq ($(findstring $(MAKEFLAGS),w),w)
PRINT_DIR = --no-print-directory
else # "make -w"
NO_SUBDIR = :
endif

ifneq ($(findstring $(MAKEFLAGS),s),s)
ifndef V
	QUIET_ASCIIDOC	= @echo '   ' ASCIIDOC $@;
	QUIET_XMLTO	= @echo '   ' XMLTO $@;
	QUIET_DB2TEXI	= @echo '   ' DB2TEXI $@;
	QUIET_DBLATEX	= @echo '   ' DBLATEX $@;
	QUIET_XSLTPROC	= @echo '   ' XSLTPROC $@;
	QUIET_GEN	= @echo '   ' GEN $@;
	QUIET_STDERR	= 2> /dev/null
	QUIET_SUBDIR0	= +@subdir=
	QUIET_SUBDIR1	= ;$(NO_SUBDIR) echo '   ' SUBDIR $$subdir; \
			  $(MAKE) $(PRINT_DIR) -C $$subdir
	export V
endif
endif

all: html man

html: $(DOC_HTML)

$(DOC_HTML) $(DOC_MAN1): asciidoc.conf

man: man1
man1: $(DOC_MAN1)

install: install-man

install-man: man
	$(INSTALL) -d -m 755 $(DESTDIR)$(man1dir)
	$(INSTALL) -m 644 $(DOC_MAN1) $(DESTDIR)$(man1dir)

install-html: html
	'$(SHELL_PATH_SQ)' ./install-webdoc.sh $(DESTDIR)$(htmldir)

../MVGIT-VERSION-FILE: .FORCE-MVGIT-VERSION-FILE
	$(QUIET_SUBDIR0)../ $(QUIET_SUBDIR1) MVGIT-VERSION-FILE

-include ../MVGIT-VERSION-FILE

#
# Determine "include::" file references in asciidoc files.
#
doc.dep : $(wildcard *.txt) build-docdep.perl
	$(QUIET_GEN)$(RM) $@+ $@ && \
	$(PERL_PATH) ./build-docdep.perl >$@+ $(QUIET_STDERR) && \
	mv $@+ $@

-include doc.dep

cmds_txt = cmds-ancillaryinterrogators.txt \
	cmds-ancillarymanipulators.txt \
	cmds-mainporcelain.txt \
	cmds-plumbinginterrogators.txt \
	cmds-plumbingmanipulators.txt \
	cmds-synchingrepositories.txt \
	cmds-synchelpers.txt \
	cmds-purehelpers.txt \
	cmds-foreignscminterface.txt

$(cmds_txt): cmd-list.made

cmd-list.made: cmd-list.perl ../command-list.txt $(MAN1_TXT)
	$(QUIET_GEN)$(RM) $@ && \
	$(PERL_PATH) ./cmd-list.perl ../command-list.txt $(QUIET_STDERR) && \
	date >$@

clean:
	$(RM) *.xml *.xml+ *.html *.html+ *.1 *.5 *.7
	$(RM) *.texi *.texi+ *.texi++ mvgit.info mvgitman.info
	$(RM) doc.dep
	$(RM) $(cmds_txt) *.made

$(MAN_HTML): %.html : %.txt
	$(QUIET_ASCIIDOC)$(RM) $@+ $@ && \
	$(ASCIIDOC) -b xhtml11 -d manpage -f asciidoc.conf \
		$(ASCIIDOC_EXTRA) -agit_version=$(MVGIT_VERSION) -o $@+ $< && \
	mv $@+ $@

%.1 %.5 %.7 : %.xml
	$(QUIET_XMLTO)$(RM) $@ && \
	xmlto -m $(MANPAGE_XSL) $(XMLTO_EXTRA) man $<

%.xml : %.txt ../MVGIT-VERSION-FILE
	$(QUIET_ASCIIDOC)$(RM) $@+ $@ && \
	$(ASCIIDOC) -b docbook -d manpage -f asciidoc.conf \
		$(ASCIIDOC_EXTRA) -amvgit_version=$(MVGIT_VERSION) -o $@+ $< && \
	mv $@+ $@

$(patsubst %,%.html,$(API_DOCS)): %.html : %.txt
	$(QUIET_ASCIIDOC)$(ASCIIDOC) -b xhtml11 -f asciidoc.conf \
		$(ASCIIDOC_EXTRA) -amvgit_version=$(MVGIT_VERSION) $*.txt

$(patsubst %.txt,%.texi,$(MAN_TXT)): %.texi : %.xml
	$(QUIET_DB2TEXI)$(RM) $@+ $@ && \
	$(DOCBOOK2X_TEXI) --to-stdout $*.xml >$@+ && \
	mv $@+ $@

$(patsubst %,%.html,$(ARTICLES)) : %.html : %.txt
	$(QUIET_ASCIIDOC)$(ASCIIDOC) $(ASCIIDOC_EXTRA) -b xhtml11 $*.txt

$(patsubst %.txt,%.html,$(wildcard howto/*.txt)): %.html : %.txt
	$(QUIET_ASCIIDOC)$(RM) $@+ $@ && \
	sed -e '1,/^$$/d' $< | $(ASCIIDOC) $(ASCIIDOC_EXTRA) -b xhtml11 - >$@+ && \
	mv $@+ $@

.PHONY: .FORCE-MVGIT-VERSION-FILE
