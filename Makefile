NAME    = yum-plugin-s3-iam
VERSION = 1.2.2
RELEASE = 1
ARCH    = noarch

RPM_TOPDIR ?= $(shell rpm --eval '%{_topdir}')

RPMBUILD_ARGS := \
	--define "name $(NAME)" \
	--define "version $(VERSION)" \
	--define "release $(RELEASE)"

.PHONY: all rpm install test

all:
	@echo "Usage: make rpm"


tarball: $(NAME)-$(VERSION).tar.gz
$(NAME)-$(VERSION).tar.gz: 
	rsync -a $(PWD)/ $(NAME)-$(VERSION)/ \
		--exclude-from=.gitignore
	tar cpzvf $@ $(NAME)-$(VERSION)

spec: $(NAME).spec
.PHONY: $(NAME).spec
$(NAME).spec:: Makefile $(NAME).spec.in
	rm -f $@
	cat $(NAME).spec.in | \
		sed "s/@@@NAME@@@/$(NAME)/g" | \
		sed "s/@@@VERSION@@@/$(VERSION)/g" | \
		sed "s/@@@RELEASE@@@/$(RELEASE)/g" > $@

.PHONY: srpm
srpm::
	@echo "Building SRPM with $(NAME).spec"
	rpmbuild --define '_topdir $(PWD)/rpmbuild' \
		--define '_sourcedir $(PWD)' \
		-bs $(NAME).spec --nodeps

rpm:: build
build:: srpm
	rpmbuild --define '_topdir $(PWD)/rpmbuild' \
		--rebuild rpmbuild/SRPMS/*.src.rpm

install:
	install -m 0755 -d $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0644 s3iam.conf $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0755 -d $(DESTDIR)/usr/lib/yum-plugins/
	install -m 0644 s3iam.py $(DESTDIR)/usr/lib/yum-plugins/

clean::
	rm -rf */
	rm -rf *.tar.gz

test: rpm
	python tests.py
