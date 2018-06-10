# Set these for specific .spec files
NAME    = yum-plugin-s3-iam
VERSION = 1.2.2
RELEASE = 2

# Build for designated operating systems
#MOCKS += epel-5-i386
MOCKS += epel-6-i386
MOCKS += epel-6-x86_64
MOCKS += epel-7-x86_64
MOCKS += fedora-27-x86_64
MOCKS += fedora-28-x86_64

.PHONY: help
help:
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
		sed "s/@@@RELEASE@@@/$(RELEASE)/g" > $@ || \
		rm -f $@

build:: rpm
rpm:: srpm
	rpmbuild --define '_topdir $(PWD)/rpmbuild' \
		--define '_sourcedir $(PWD)' \
		-bb $(NAME).spec

.PHONY: srpm
srpm:: tarball
srpm:: $(NAME).spec
	@echo "Building SRPM with $?"
	rpmbuild --define '_topdir $(PWD)/rpmbuild' \
		--define '_sourcedir $(PWD)' \
		-bs $(NAME).spec --nodeps

.PHONY: install
install:
	install -m 0755 -d $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0644 s3iam.conf $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0755 -d $(DESTDIR)/usr/lib/yum-plugins/
	install -m 0644 s3iam.py $(DESTDIR)/usr/lib/yum-plugins/

mocks: $(MOCKS)
.PHONY: $(MOCKS)
$(MOCKS):: /usr/bin/mock
$(MOCKS):: srpm
	mock -r $@ --resultdir=$(PWD)/$@ \
		rpmbuild/SRPMS/$(NAME)-$(VERSION)-$(RELEASE).*.src.rpm

clean::
	rm -rf */
	rm -rf *.tar.gz
	rm -rf *.spec

.PHONY: test
test: rpm
	python tests.py
