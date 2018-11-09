NAME    = yum-plugin-s3-iam
VERSION = 1.2.2
RELEASE = 1
ARCH    = noarch

RPM_TOPDIR ?= $(CURDIR)/build

RPMBUILD_ARGS := \
	--define "name $(NAME)" \
	--define "version $(VERSION)" \
	--define "release $(RELEASE)" \
	--define="_topdir $(CURDIR)/build"

REPO_URL = s3://bv-nexus-public-artifacts/yum-repo/

.PHONY: all rpm install test

all:
	@echo "Usage: make rpm"

clean:
	rm -Rf build

install:
	install -m 0755 -d $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0644 s3iam.conf $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0755 -d $(DESTDIR)/usr/lib/yum-plugins/
	install -m 0644 s3iam.py $(DESTDIR)/usr/lib/yum-plugins/

tgz: clean
	mkdir -p $(RPM_TOPDIR)/SOURCES
	mkdir -p $(RPM_TOPDIR)/SPECS
	mkdir -p $(RPM_TOPDIR)/BUILD
	mkdir -p $(RPM_TOPDIR)/RPMS/$(ARCH)
	mkdir -p $(RPM_TOPDIR)/SRPMS
	rm -Rf $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION)
	rsync -r --exclude='build' . $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION)
	tar czf $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION).tar.gz -C $(RPM_TOPDIR)/SOURCES $(NAME)-$(VERSION)

rpm: tgz
	rm -Rf $(RPM_TOPDIR)/SOURCES/$(NAME)-$(VERSION)
	cp $(NAME).spec $(RPM_TOPDIR)/SPECS/
	rpmbuild --target=linux $(RPMBUILD_ARGS) -ba --clean $(NAME).spec

test:
	python tests.py

e2e_local: rpm
	cp s3iam.repo /etc/yum.repos.d/
	yum -y install $(RPM_TOPDIR)/RPMS/$(ARCH)/$(NAME)-$(VERSION)*.rpm
	yum -y install cabertoss-artifacts

release: rpm
	mkdir -p $(RPM_TOPDIR)/RELEASE
	aws s3 cp $(REPO_URL) $(RPM_TOPDIR)/RELEASE --recursive
	cp $(RPM_TOPDIR)/RPMS/$(ARCH)/$(NAME)-$(VERSION)*.rpm $(RPM_TOPDIR)/RELEASE
	createrepo --update $(RPM_TOPDIR)/RELEASE
	aws s3 sync $(RPM_TOPDIR)/RELEASE $(REPO_URL) --acl public-read

e2e_release:
	cp s3iam.repo /etc/yum.repos.d/
	yum -y install cabertoss-artifacts
