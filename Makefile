# set EXTRAREV to append something to the RPM revision, e.g. EXTRAREV=.is24

# this goes into the src archive and this is relevant for the revision
TOPLEVEL = LICENSE  Makefile  NOTICE  README.md  s3iam.conf  s3iam.py  s3iam.repo  tests.py  yum-plugin-s3-iam.spec

GITREV := HEAD

NAME=yum-plugin-s3-iam
ARCH=noarch
VERSION := $(shell git rev-list $(GITREV) -- $(TOPLEVEL) 2>/dev/null| wc -l)
RELEASE := 1$(EXTRAREV)
PV := $(NAME)-$(VERSION)

.PHONY: all test srpm clean rpm info rpminfo install

all: rpminfo
	ls -l dist/

install:
	install -m 0755 -d $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0644 s3iam.conf $(DESTDIR)/etc/yum/pluginconf.d/
	install -m 0755 -d $(DESTDIR)/usr/lib/yum-plugins/
	install -m 0644 s3iam.py $(DESTDIR)/usr/lib/yum-plugins/

tgz: clean
	@echo "Creating TAR.GZ"
	mkdir -p dist build/$(PV) build/BUILD
	cp -r $(TOPLEVEL) build/$(PV)
	mv build/$(PV)/*.spec build/
	sed -i -e "s/__VERSION__/$(VERSION)/" -e "s/__RELEASE__/$(RELEASE)/" -e "s/__NAME__/$(NAME)/" build/*.spec build/$(PV)/*.py
	tar -czf dist/$(PV).tar.gz -C build $(PV)

srpm: tgz
	@echo "Creating SOURCE RPM"
	rpmbuild $(RPMBUILD_OPTS) --define="_topdir $(CURDIR)/build" --define="_sourcedir $(CURDIR)/dist" --define="_srcrpmdir $(CURDIR)/dist" --nodeps -bs build/*.spec

rpm: srpm
	@echo "Creating BINARY RPM"
	ln -svf ../dist build/noarch
	rpmbuild $(RPMBUILD_OPTS) --define="_topdir $(CURDIR)/build" --define="_rpmdir %{_topdir}" --rebuild $(CURDIR)/dist/*.src.rpm
	@echo
	@echo
	@echo
	@echo 'WARNING! THIS RPM IS NOT INTENDED FOR PRODUCTION USE. PLEASE USE rpmbuild --rebuild dist/*.src.rpm TO CREATE A PRODUCTION RPM PACKAGE!'
	@echo
	@echo
	@echo

info: rpminfo

rpminfo: rpm
	rpm -qip dist/*.noarch.rpm

rpmrepo: rpm
	repoclient uploadto "$(TARGET_REPO)" dist/*.rpm
	echo "##teamcity[buildStatus text='{build.status.text} RPM Version $(shell rpm -qp dist/*src.rpm --queryformat "%{VERSION}-%{RELEASE}") in $(TARGET_REPO)']"

clean:
	rm -Rf dist build test



# todo: create debian/RPM changelog automatically, e.g. with git-dch --full --id-length=10 --ignore-regex '^fixes$' -S -s 68809505c5dea13ba18a8f517e82aa4f74d79acb src doc *.spec

