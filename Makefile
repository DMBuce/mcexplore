SHELL = /bin/sh

# root for installation
prefix      = /usr/local
exec_prefix = ${prefix}

# executables
bindir     = ${exec_prefix}/bin
sbindir    = ${exec_prefix}/sbin
libexecdir = ${exec_prefix}/libexec

# data
datarootdir    = ${prefix}/share
datadir        = ${datarootdir}
sysconfdir     = ${prefix}/etc
sharedstatedir = ${prefix}/com
localstatedir  = ${prefix}/var

# misc
includedir    = ${prefix}/include
oldincludedir = /usr/include
docdir        = ${datarootdir}/doc/${PACKAGE_TARNAME}
infodir       = ${datarootdir}/info
libdir        = ${exec_prefix}/lib
localedir     = ${datarootdir}/locale
mandir        = ${datarootdir}/man
man1dir       = $(mandir)/man1
man2dir       = $(mandir)/man2
man3dir       = $(mandir)/man3
man4dir       = $(mandir)/man4
man5dir       = $(mandir)/man5
man6dir       = $(mandir)/man6
man7dir       = $(mandir)/man7
man8dir       = $(mandir)/man8
man9dir       = $(mandir)/man9
manext        = .1
srcdir        = .

INSTALL         = /usr/bin/install -c
INSTALL_PROGRAM = ${INSTALL}
INSTALL_DATA    = ${INSTALL} -m 644

LN_S        = ln -s
SED_INPLACE = sed -i

INSTALL_DIRS  = $(DESTDIR)$(bindir) $(DESTDIR)$(man1dir)

.PHONY: all
all: doc

.PHONY: doc
doc: mcexplore.1

.PHONY: install
install: $(INSTALL_DIRS) doc $(DESTDIR)$(bindir)/mcexplore $(DESTDIR)$(man1dir)/mcexplore.1

.PHONY: html
html: mcexplore.1.html

mcexplore.1: mcexplore.py
	argparse-manpage \
		--pyfile $< \
		--function getParser \
		--author 'DMBuce <https://github.com/DMBuce> and similardilemma' \
		--author-email 'https://github.com/similardilemma' \
		--project-name mcexplore \
		--url https://github.com/dmbuce/mcexplore \
		> mcexplore.1
	sed -i '1s/.*/.TH MCEXPLORE "1" $(shell date +%F) "\\ \\\&" "\\ \\\&"/' mcexplore.1

$(DESTDIR)$(bindir)/mcexplore: mcexplore.py
	$(INSTALL) -m755 $< $@

$(DESTDIR)$(man1dir)/mcexplore.1: mcexplore.1
	$(INSTALL_DATA) $< $@

$(INSTALL_DIRS):
	$(INSTALL) -d $@

%.html: %.txt
	asciidoc -a toc -a icons -a max-width=960px $<

