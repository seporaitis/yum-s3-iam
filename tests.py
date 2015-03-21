# Copyright 2012, Julius Seporaitis
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import os
import tempfile
import glob
import shutil
import StringIO
import urllib2
import unittest
import rpm
import yum
import createrepo
sys.path.append('.')
import s3iam


PACKAGE_NAME = 'yum-plugin-s3-iam'
RPM_DIR = rpm.expandMacro('%_rpmdir')
try:
    RPM_FILE = glob.glob(os.path.join(RPM_DIR, 'noarch', PACKAGE_NAME + '*.rpm'))[0]
except IndexError:
    RPM_FILE = None


class MDCallback(object):
    def log(self, msg):
        pass


class YumTestCase(unittest.TestCase):

    baseurl = 'http://test.s3.amazonaws.com/noarch/'

    def _createrepo(self):
        mdconf = createrepo.MetaDataConfig()
        mdconf.directory = self.tmpdir
        mdgen = createrepo.MetaDataGenerator(mdconf, MDCallback())
        mdgen.doPkgMetadata()
        mdgen.doRepoMetadata()
        mdgen.doFinalMove()

    def _mock_urlopen(self, url):
        if hasattr(url, 'get_full_url'):
            url = url.get_full_url()
        if 'security-credentials' in url:
            return StringIO.StringIO('{"AccessKeyId":"k", "SecretAccessKey":"x", "Token": "t"}')
        else:
            if 'broken' in url:
                raise urllib2.HTTPError(url, 403, 'Forbidden', None, None)
            # return files from local repo created with _createrepo
            assert url.startswith(self.baseurl)
            return open(os.path.join(self.tmpdir, url[len(self.baseurl):]))

    def _init_yum(self, baseurl=None, **kwargs):
        cwd = os.getcwd()
        yum.config.StartupConf.pluginpath =\
            yum.config.StartupConf.pluginconfpath = yum.config.ListOption([cwd])
        yumbase = yum.YumBase()
        yumbase.preconf.disabled_plugins = '*'
        yumbase.preconf.enabled_plugins = ['s3iam']
        yumbase.preconf.debuglevel = 0
        yumbase.conf.cachedir = os.path.join(self.tmpdir, '_cache')
        yumbase.repos.disableRepo('*')
        yumbase.add_enable_repo('s3test', [baseurl or self.baseurl],
                                s3_enabled=True, _async=True, **kwargs)
        return yumbase

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Set up urlopen mock:
        urllib2.urlopen, urllib2.urlopen_ = self._mock_urlopen, urllib2.urlopen

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        urllib2.urlopen = urllib2.urlopen_

    # @unittest.skipIf(RPM_FILE is None, 'Rpm file required')
    def test_yum_available(self):
        if not RPM_FILE:
            print >>sys.stderr, 'Skipping:', 'Rpm file required'
            return
        # copy rpm file to tmpdir and create repodata
        shutil.copyfile(RPM_FILE, os.path.join(self.tmpdir, 's3iam.rpm'))
        self._createrepo()

        yumbase = self._init_yum()
        available = yumbase.doPackageLists().available
        self.assertEqual([p.name for p in available], [PACKAGE_NAME])

    def test_s3_scheme(self):
        if not RPM_FILE:
            print >>sys.stderr, 'Skipping:', 'Rpm file required'
            return
        # copy rpm file to tmpdir and create repodata
        shutil.copyfile(RPM_FILE, os.path.join(self.tmpdir, 's3iam.rpm'))
        self._createrepo()

        yumbase = self._init_yum(
            baseurl='s3://test.s3.amazonaws.com',
        )
        available = yumbase.doPackageLists().available
        self.assertEqual([p.name for p in available], [PACKAGE_NAME])

    def test_repo_unavailable(self):
        self._createrepo()

        # Throws RepoError exception
        yumbase = self._init_yum(
            baseurl='http://broken.s3.amazonaws.com',
            skip_if_unavailable=False,
        )
        self.assertRaises(yum.Errors.RepoError,
                          lambda: yumbase.doPackageLists().available)

        # No exception when skip_if_unavailable
        yumbase = self._init_yum(
            baseurl='http://broken.s3.amazonaws.com',
            skip_if_unavailable=True,
        )
        yumbase.doPackageLists().available


class S3GrabberTest(unittest.TestCase):

    def test_example_sign(self):
        """Test with example data"""
        grabber = s3iam.S3Grabber("http://johnsmith.s3.amazonaws.com/")
        grabber.access_key = "AKIAIOSFODNN7EXAMPLE"
        grabber.secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        grabber.token = 'None'
        request = grabber._request("photos/puppy.jpg")
        signature = grabber.sign(request, timeval=(2013, 1, 1, 0, 0, 0, 0, 0, 0))
        self.assertEqual(signature.strip(), "g28R8sx2k7a5lW/9jMfCNfnMHjc=")


if __name__ == '__main__':
    unittest.main()
