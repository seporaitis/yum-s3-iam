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
from mock import patch, ANY, MagicMock


PACKAGE_NAME = 'yum-plugin-s3-iam'
RPM_DIR = rpm.expandMacro('%_rpmdir')
try:
    RPM_FILE = glob.glob(os.path.join(RPM_DIR, 'noarch', PACKAGE_NAME + '*.rpm'))[0]
except IndexError:
    RPM_FILE = None


class MDCallback(object):
    def log(self, msg):
        pass

    def errorlog(self, msg):
        pass


class YumTestCase(unittest.TestCase):

    baseurl = 'https://test.s3.amazonaws.com/noarch/'

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

    def test_repo_unavailable(self):
        self._createrepo()

        # Throws RepoError exception
        yumbase = self._init_yum(
            baseurl='https://broken.s3.amazonaws.com',
            retries=0, skip_if_unavailable=False,
        )
        self.assertRaises(yum.Errors.RepoError,
                          lambda: yumbase.doPackageLists().available)

        # No exception when skip_if_unavailable
        yumbase = self._init_yum(
            baseurl='https://broken.s3.amazonaws.com',
            retries=0, skip_if_unavailable=True,
        )
        yumbase.doPackageLists().available


class S3GrabberTest(unittest.TestCase):

    def test_example_sign(self):
        """Test with example data"""
        # See http://docs.aws.amazon.com/AmazonS3/latest/dev/RESTAuthentication.html
        grabber = s3iam.S3Grabber("http://johnsmith.s3.amazonaws.com/")
        grabber.access_key = "AKIAIOSFODNN7EXAMPLE"
        grabber.secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        grabber.token = None
        request = grabber._request("/photos/puppy.jpg", timeval=(2007, 3, 27, 19, 36, 42, 1, 0, 0))
        self.assertEqual(request.get_header('Authorization').strip(),
                         "AWS " + grabber.access_key + ":bWq2s1WEIj+Ydj0vQ697zp+IXMU=")

class UrlTests(unittest.TestCase):
    def test_urls(self):
        (b, r, p) = s3iam.parse_url('https://foo.s3.amazonaws.com/path')
        self.assertEqual(b, 'foo')
        self.assertEqual(r, None)
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://www.foo.com.s3.amazonaws.com/path')
        self.assertEqual(b, 'www.foo.com')
        self.assertEqual(r, None)
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://foo.s3-us-west-2.amazonaws.com/path')
        self.assertEqual(b, 'foo')
        self.assertEqual(r, 'us-west-2')
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://foo.s3.us-west-2.amazonaws.com/path')
        self.assertEqual(b, 'foo')
        self.assertEqual(r, 'us-west-2')
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://foo.s3-website.us-west-2.amazonaws.com/path')
        self.assertEqual(b, 'foo')
        self.assertEqual(r, 'us-west-2')
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://s3.amazonaws.com/bar/path')
        self.assertEqual(b, 'bar')
        self.assertEqual(r, 'us-east-1')
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://s3-us-west-1.amazonaws.com/bar/path')
        self.assertEqual(b, 'bar')
        self.assertEqual(r, 'us-west-1')
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://s3.cn-north-1.amazonaws.com.cn/bar/path')
        self.assertEqual(b, 'bar')
        self.assertEqual(r, 'cn-north-1')
        self.assertEqual(p, '/path')

        (b, r, p) = s3iam.parse_url('https://s3.dualstack.us-west-1.amazonaws.com/chicken-little/path')
        self.assertEqual(b, 'chicken-little')
        self.assertEqual(r, 'us-west-1')
        self.assertEqual(p, '/path')

class S3RepositoryTest(unittest.TestCase):

    def setUp(self):
        self.orig_http_proxy = os.environ['http_proxy'] if 'http_proxy' in os.environ else None
        os.environ['https_proxy'] = 'http://https_proxy_host:https_proxy_port'
        self.orig_https_proxy = os.environ['https_proxy'] if 'https_proxy' in os.environ else None
        os.environ['http_proxy'] = 'http://http_proxy_host:http_proxy_port'
        self.repo = MagicMock(
            baseurl = 'https://s3.cn-north-1.amazonaws.com.cn/bar/path',
            name = 'test repo',
            region = 'cn-north-1',
            basecachedir = '',
            gpgcheck = False,
            gpgkey = None,
            key_id = None,
            secret_key = None,
            enablegroups = False,
            delegated_role = None,
            retries = 1,
            backoff = None,
            delay = 0,
            mirrorlist = None,
            proxy = None
            )

    def tearDown(self):
        if self.orig_https_proxy is not None:
            os.environ['https_proxy'] = self.orig_https_proxy
        if self.orig_http_proxy is not None:
            os.environ['http_proxy'] = self.orig_http_proxy

    @patch('s3iam.urllib2')
    def test_config_proxy_from_env(self, urllib2_mock):
        s3_repo = s3iam.S3Repository('repo-id', self.repo)
        urllib2_mock.ProxyHandler.assert_called_once_with({
            'http':'http://http_proxy_host:http_proxy_port',
            'https':'http://https_proxy_host:https_proxy_port'
            })
        urllib2_mock.build_opener.assert_called_once_with(urllib2_mock.ProxyHandler.return_value)
        urllib2_mock.install_opener.assert_called_once_with(ANY)

    @patch('s3iam.urllib2')
    def test_config_proxy_from_yum_conf(self, urllib2_mock):
        del(os.environ['http_proxy'])
        del(os.environ['https_proxy'])
        self.repo.proxy = 'http://same_proxy_for_all:port'
        s3_repo = s3iam.S3Repository('repo-id', self.repo)
        urllib2_mock.ProxyHandler.assert_called_once_with({
            'http':'http://same_proxy_for_all:port',
            'https':'http://same_proxy_for_all:port'
            })
        urllib2_mock.build_opener.assert_called_once_with(urllib2_mock.ProxyHandler.return_value)
        urllib2_mock.install_opener.assert_called_once_with(ANY)


if __name__ == '__main__':
    unittest.main()
