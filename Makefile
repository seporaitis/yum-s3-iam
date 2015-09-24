NAME				= yum-plugin-s3-iam
VERSION			= 1.0
RELEASE			= 2
ARCH				= noarch

RPM_TOPDIR ?= $(shell rpm --eval '%{_topdir}')

RPMBUILD_ARGS := \
	--define "name $(NAME)" \
	--define "version $(VERSION)" \
	--define "release $(RELEASE)"

.PHONY: all rpm install test

all:
	@echo "Usage: make rpm"

install:
	install -m 0755 -d $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0644 s3iam.conf $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0755 -d $(DESTDIR)/usr/lib/yum-plugins/
	install -m 0644 s3iam.py $(DESTDIR)/usr/lib/yum-plugins/

rpm:
	mkdir -p $(RPM_TOPDIR)/SOURCES
	mkdir -p $(RPM_TOPDIR)/SPECS
	mkdir -p $(RPM_TOPDIR)/BUILD
	mkdir -p $(RPM_TOPDIR)/RPMS/$(ARCH)
	mkdir -p $(RPM_TOPDIR)/SRPMS
	rm -Rf $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION)
	cp -r . $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION)
	tar czf $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION).tar.gz -C $(RPM_TOPDIR)/SOURCES --exclude ".git" $(NAME)-$(VERSION)
	rm -Rf $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION)
	cp $(NAME).spec $(RPM_TOPDIR)/SPECS/
	rpmbuild $(RPMBUILD_ARGS) -ba --clean $(NAME).spec

test: rpm
	python tests.py
