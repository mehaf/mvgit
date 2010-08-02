# The default target of this Makefile is...
all::

MVGIT-VERSION-FILE: .FORCE-MVGIT-VERSION-FILE
	@$(SHELL_PATH) ./MVGIT-VERSION-GEN
-include MVGIT-VERSION-FILE

# Among the variables below, these:
#   mandir
# can be specified as a relative path some/where/else;
# this is interpreted as relative to $(prefix) and "git" at
# runtime figures out where they are based on the path to the executable.
# This can help installing the suite in a relocatable way.

prefix = /usr/local
bindir_relative = bin
bindir = $(prefix)/$(bindir_relative)
mandir = share/man
# DESTDIR=

export prefix bindir

RM = rm -f
INSTALL = install

### --- END CONFIGURATION SECTION ---

# Guard against environment variables
PROGRAMS =
SCRIPT_SH =
SCRIPT_PYTHON =

SCRIPT_SH += git-bulk-cherry-mv.sh
SCRIPT_SH += git-commit-mv.sh
SCRIPT_SH += git-push-mv.sh
SCRIPT_SH += git-quiltexport-mv.sh
SCRIPT_SH += git-signoff-mv.sh

SCRIPT_PYTHON += git-analyze-changes.py
SCRIPT_PYTHON += git-changes.py
SCRIPT_PYTHON += git-diff-limb.py
SCRIPT_PYTHON += git-mvl6-releasify.py
SCRIPT_PYTHON += git-limb.py
SCRIPT_PYTHON += git-log-limb.py
SCRIPT_PYTHON += git-ls-limb.py
SCRIPT_PYTHON += git-merge-limb.py
SCRIPT_PYTHON += git-provenance.py
SCRIPT_PYTHON += git-push-limb.py
SCRIPT_PYTHON += git-rebase-limb.py
SCRIPT_PYTHON += git-signoff-limb.py

SCRIPTS = $(patsubst %.sh,%,$(SCRIPT_SH)) \
	  $(patsubst %.py,%,$(SCRIPT_PYTHON))

# what 'all' will build and 'install' will install, in bindri
ALL_PROGRAMS = $(PROGRAMS) $(SCRIPTS)

# not built by 'all, but 'install' will install in bindir
OTHER_INSTALL = mvgitlib.py

# Set paths to tools early so that they can be used for version tests.
ifndef SHELL_PATH
	SHELL_PATH = /bin/sh
endif
ifndef PYTHON_PATH
	PYTHON_PATH = /usr/bin/python
endif

export PYTHON_PATH

ifneq ($(findstring $(MAKEFLAGS),w),w)
PRINT_DIR = --no-print-directory
else # "make -w"
NO_SUBDIR = :
endif

ifneq ($(findstring $(MAKEFLAGS),s),s)
ifndef V
	QUIET_GEN      = @echo '   ' GEN $@;
	QUIET_SUBDIR0  = +@subdir=
	QUIET_SUBDIR1  = ;$(NO_SUBDIR) echo '   ' SUBDIR $$subdir; \
			 $(MAKE) $(PRINT_DIR) -C $$subdir
	export V
	export QUIET_GEN
	export QUIET_BUILT_IN
endif
endif

ifdef ASCIIDOC8
	export ASCIIDOC8
endif

# Shell quote (do not use $(call) to accommodate ancient setups);

DESTDIR_SQ = $(subst ','\'',$(DESTDIR))
bindir_SQ = $(subst ','\'',$(bindir))
bindir_relative_SQ = $(subst ','\'',$(bindir_relative))

SHELL_PATH_SQ = $(subst ','\'',$(SHELL_PATH))
PYTHON_PATH_SQ = $(subst ','\'',$(PYTHON_PATH))

export INSTALL DESTDIR SHELL_PATH


### Build rules

SHELL = $(SHELL_PATH)

all:: shell_compatibility_test $(ALL_PROGRAMS) $(BUILT_INS) $(OTHER_PROGRAMS)
ifneq (,$X)
	$(foreach p,$(patsubst %$X,%,$(filter %$X,$(ALL_PROGRAMS)), test '$p' -ef '$p$X' || $(RM) '$p';)
endif

please_set_SHELL_PATH_to_a_more_modern_shell:
	@$$(:)

shell_compatibility_test: please_set_SHELL_PATH_to_a_more_modern_shell

$(patsubst %.sh,%,$(SCRIPT_SH)) : % : %.sh
	$(QUIET_GEN)$(RM) $@ $@+ && \
	sed -e '1s|#!.*/sh|#!$(SHELL_PATH_SQ)|' \
	    -e 's|@SHELL_PATH@|$(SHELL_PATH_SQ)|' \
	    -e 's/@@MVGIT_VERSION@@/$(MVGIT_VERSION)/g' \
	    $@.sh >$@+ && \
	chmod +x $@+ && \
	mv $@+ $@

$(patsubst %.py,%,$(SCRIPT_PYTHON)) : % : %.py
	$(QUIET_GEN)$(RM) $@ $@+ && \
	sed -e '1s|#!.*/python|#!$(PYTHON_PATH_SQ)|' \
	    -e 's/@@MVGIT_VERSION@@/$(MVGIT_VERSION)/g' \
	    $@.py >$@+ && \
	chmod +x $@+ && \
	mv $@+ $@

# These can record MVGIT_VERSION
$(patsubst %.sh, %, $(SCRIPT_SH)) \
	$(patsubst %.py,%,$(SCRIPT_PYTHON)) \
	: MVGIT-VERSION-FILE

doc:
	$(MAKE) -C Documentation all

man:
	$(MAKE) -C Documentation man

html:
	$(MAKE) -C Documentation html

info:
	$(MAKE) -C Documentation info

pdf:
	$(MAKE) -C Documentation pdf


### Installation rules

remove-oldversions:
	$(QUIET_GEN)for p in $(ALL_PROGRAMS) $(OTHER_INSTALL); do \
			fp="$$(git --exec-path)/$$p"; \
			test -f $$fp && $(RM) $$fp; \
			true; \
		done

install: all remove-oldversions
	$(INSTALL) -d -m 755 '$(DESTDIR_SQ)$(bindir_SQ)'
	$(INSTALL) $(ALL_PROGRAMS) $(OTHER_INSTALL) '$(DESTDIR_SQ)$(bindir_SQ)'

install-doc:
	$(MAKE) -C Documentation install

install-man:
	$(MAKE) -C Documentation install-man

install-html:
	$(MAKE) -C Documentation install-html

install-info:
	$(MAKE) -C Documentation install-info

install-pdf:
	$(MAKE) -C Documentation install-pdf


### Cleaning rules

distclean: clean

clean:
	$(RM) $(ALL_PROGRAMS)
	$(RM) *.spec *.pyc *.pyo */*.pyc */*.pyo common-cmds.h TAGS tags cscope*
	$(RM) -r autom4te.cache
	$(RM) -r .doc-tmp-dir
	$(MAKE) -C Documentation/ clean
	$(RM) MVGIT-VERSION-FILE

.PHONY: all install clean strip
.PHONY: shell_compatibility_test please_set_SHELL_PATH_to_a_more_modern_shell
.PHONY: .FORCE-MVGIT-VERSION-FILE
.PHONY: remove-oldversions
