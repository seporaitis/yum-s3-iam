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

sys.path.append('/usr/lib/yum-plugins')
import s3iam


# Allows supressing messages from MetaDataGenerator
class MDCallback(object):
    def log(self, msg):
        pass
    def errorlog(self, msg):
        pass


class YumTestCase(unittest.TestCase):

    MOCK_HOST_BASEURL = 'http://test.s3.amazonaws.com/noarch/'
    MOCK_PATH_BASEURL = 'http://s3.amazonaws.com/noarch/test/'
    MOCK_BASEURLS = [MOCK_HOST_BASEURL, MOCK_PATH_BASEURL]

    MOCK_BROKEN_BASEURL = 'http://broken.s3.amazonaws.com/test'

    def _createrepo(self, package_name):
        err_msg = None
        try:
            import createrepo
            rpm_dir = rpm.expandMacro('%_rpmdir')
            rpm_file = glob.glob(os.path.join(rpm_dir,
                                              'noarch',
                                              package_name + '*.rpm'
                                              ))[0]
            shutil.copyfile(rpm_file, os.path.join(self.tmpdir, 's3iam.rpm'))

        except IndexError:
            err_msg = 'Skipping: Createrepo not found!'

        except ImportError:
            err_msg = 'Skipping:', 'RPM file %s not found' % package_name

        if err_msg:
            print >> sys.stderr, err_msg
            return

        mdconf = createrepo.MetaDataConfig()
        mdconf.directory = self.tmpdir
        mdgen = createrepo.MetaDataGenerator(mdconf, MDCallback())
        mdgen.doPkgMetadata()
        mdgen.doRepoMetadata()
        mdgen.doFinalMove()
        return mdgen

    def _mock_urlopen(self, url):
        """ Provides stub responses for urlopen based on the URL """
        if hasattr(url, 'get_full_url'):
            url = url.get_full_url()

        if 'security-credentials' in url:
            pload = '{"AccessKeyId":"k", "SecretAccessKey":"x", "Token":"t"}'
            return StringIO.StringIO(pload)

        if 'broken' in url:
            raise urllib2.HTTPError(url, 403, 'Forbidden', None, None)

        # return files from local repo created with _createrepo
        assert any([url.startswith(u) for u in self.MOCK_BASEURLS])
        for bu in self.MOCK_BASEURLS:
            if url.startswith(bu):
                return open(os.path.join(self.tmpdir, url[len(bu):]))

    def _init_yum(self):
        # this allows both testing where the plugin, conf and test
        # are spread among different paths
        paths = [os.getcwd(),
                 '/usr/lib/yum-plugins',
                 '/etc/yum/pluginconf.d']
        yum.config.StartupConf.pluginpath = yum.config.ListOption(paths)
        yum.config.StartupConf.pluginconfpath = yum.config.ListOption(paths)
        yumbase = yum.YumBase()
        yumbase.preconf.disabled_plugins = '*'
        yumbase.preconf.enabled_plugins = ['s3iam']
        yumbase.preconf.debuglevel = 1
        yumbase.conf.cachedir = os.path.join(self.tmpdir, '_cache')
        yumbase.repos.disableRepo('*')

        return yumbase

    def _add_enable_s3_repo(self, name, **kwargs):
        self.yumbase.add_enable_repo(name, s3_enabled=True, **kwargs)
        self.yumbase.repos.doSetup(thisrepo=name)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        # Set up urlopen mock
        urllib2.urlopen, urllib2.urlopen_ = self._mock_urlopen, urllib2.urlopen
        self.yumbase = self._init_yum()
        # Set up mock logger
        s3iam.verbose_logger, s3iam.verbose_logger_ = CountingLogger, s3iam.verbose_logger

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        urllib2.urlopen = urllib2.urlopen_
        CountingLogger.reset()
        s3iam.verbose_logger = s3iam.verbose_logger_

    def test_repo_list_returns_valid_package_with_host_baseurl(self):
        """
            Make requests with s3 plugin to a stubbed repo in /tmp
        """

        # create repository with the one rpm package
        # _mock_urlopen will use that metadata
        package_name = 'yum-plugin-s3-iam'
        if not self._createrepo(package_name=package_name):
            return

        self._add_enable_s3_repo('s3test', baseurl=self.MOCK_PATH_BASEURL)
        available = self.yumbase.doPackageLists().available
        self.assertEqual([p.name for p in available], [package_name])

    def test_repo_list_returns_valid_package_with_path_baseurl(self):
        """
            Make requests with s3 plugin to a stubbed repo in /tmp
        """

        # create repository with the one rpm package
        # _mock_urlopen will use that metadata
        package_name = 'yum-plugin-s3-iam'
        if not self._createrepo(package_name=package_name):
            return

        self._add_enable_s3_repo('s3test', baseurl=self.MOCK_PATH_BASEURL)
        available = self.yumbase.doPackageLists().available
        self.assertEqual([p.name for p in available], [package_name])

    def test_repo_unavailable_throws_exception_without_retry(self):
        """
            Setting retry to < 1 will cause no retries.
            Currently infinite retry with -1 is not supported.
            If you would like to schedule infinite-like time please set
            big enough number of retries
        """
        self._add_enable_s3_repo(
            's3test',
            baseurl='http://broken.s3.amazonaws.com',
            retries=0,
            skip_if_unavailable=False,
        )
        self.assertRaises(yum.Errors.RepoError, self.yumbase.doPackageLists)

    def test_repo_unavailable_throws_exception_with_retry(self):
        """
            Test retry logic without waiting default number of retries
        """

        retries = 3
        backoff = 1
        delay = 1

        self._add_enable_s3_repo(
            's3test',
            baseurl=self.MOCK_BROKEN_BASEURL,
            retries=retries,
            delay=delay,
            backoff=backoff,
            skip_if_unavailable=False,
        )

        try:
            self.yumbase.doPackageLists()
        except yum.Errors.RepoError, e:
            pass

        s3testrepo = [r for r in self.yumbase.repos.listEnabled()
                      if r.name == 's3test'][0]
        self.assertEqual(s3testrepo.retries, retries)
        self.assertEqual(s3testrepo.backoff, backoff)
        self.assertEqual(s3testrepo.delay, delay)

        # Retry message: 8_HTTP Error 403: Forbidden, Retry attempt
        retry_msgs = [m for m in s3iam.verbose_logger.counter.keys() if
                      m.find('Forbidden, Retry attempt') > 0]
        self.assertEqual(len(retry_msgs), retries)

    def test_repo_unavailable_skips_quietly(self):
        # No exception when skip_if_unavailable
        self._add_enable_s3_repo(
            's3test',
            baseurl=self.MOCK_BROKEN_BASEURL,
            retries=0,
            skip_if_unavailable=True,
        )

        self.assertEqual(self.yumbase.doPackageLists().available, [])

    def test_repo_basic_options(self):
        skip_if_unavailable = True

        self._add_enable_s3_repo(
            's3test',
            baseurl=self.MOCK_BROKEN_BASEURL,
            skip_if_unavailable=skip_if_unavailable,
        )

        s3testrepo = [r for r in self.yumbase.repos.listEnabled()
                      if r.name == 's3test'][0]
        self.assertEquals(s3testrepo.baseurl, [self.MOCK_BROKEN_BASEURL])
        self.assertEquals(s3testrepo.skip_if_unavailable, skip_if_unavailable)

    def test_repo_disable_on_runtime_should_omit(self):
        self._add_enable_s3_repo(
            's3test',
            baseurl=self.MOCK_BROKEN_BASEURL,
        )

        repos = self.yumbase._getRepos()

        # simulate run-time disable with --disablerepo=s3test
        repos.disableRepo('s3test')
        # s3 repo should have been the only one; now it should not be present
        self.assertEquals(repos.listEnabled(), [])

    def test_repo_default_attributes(self):
        self._add_enable_s3_repo(
            's3test',
            baseurl=self.MOCK_BROKEN_BASEURL
        )

        s3testrepo = [r for r in self.yumbase.repos.listEnabled()
                      if r.name == 's3test'][0]

        self.assertEquals(s3testrepo.retries, 10)
        self.assertEquals(s3testrepo.enablegroups, True)
        self.assertEquals(s3testrepo.metadata_expire, 0)
        self.assertEquals(s3testrepo.gpgcheck, True)

    def test_repo_unsupported_attribute_proxy(self):
        self.assertRaises(yum.plugins.PluginYumExit,
                          lambda: self._add_enable_s3_repo(
                                    's3test',
                                    baseurl=self.MOCK_BROKEN_BASEURL,
                                    proxy='http://proxy.com:8080/invalid'
                          ))

    def test_repo_unsupported_attribute_mirrorlist(self):
        self.assertRaises(yum.plugins.PluginYumExit,
                          lambda: self._add_enable_s3_repo(
                                    's3test',
                                    baseurl=self.MOCK_BROKEN_BASEURL,
                                    mirrorlist='http://somewhere.com/invalid'
                          ))

    def skipIfNoKeepcache(f):
        """
        Decorator to skip tests for keepcache on not supported yum
        """
        if hasattr(yum.config.RepoConf, 'keepcache'):
            return f
        return lambda self: 0

    @skipIfNoKeepcache
    def test_repo_inherited_attributes(self):
        self._add_enable_s3_repo(
            's3test',
            baseurl=self.MOCK_BROKEN_BASEURL
        )

        s3testrepo = [r for r in self.yumbase.repos.listEnabled()
                      if r.name == 's3test'][0]

        self.assertEquals(s3testrepo.keepcache, True)


class UtilsTest(unittest.TestCase):
    def test_get_resource_with_bucket_host_url(self):
        url = "https://bucket.s3-external-1.amazonaws.com/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), 'bucket')
        self.assertEquals(s3iam.get_resource(url), "/path")

    def test_get_resource_with_bucket_host_url_double_s3(self):
        url = "https://s3bucket.s3-external-1.amazonaws.com/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), 's3bucket')
        self.assertEquals(s3iam.get_resource(url), "/path")

    def test_get_resource_with_bucket_host_url_with_dots(self):
        url = "https://s3bucket.with.dots.s3-external-1.amazonaws.com/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url),
                          's3bucket.with.dots')
        self.assertEquals(s3iam.get_resource(url), "/path")

    def test_get_resource_with_bucket_host_url_regional(self):
        url = "https://bucket.s3-east-1.amazonaws.com/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), 'bucket')
        self.assertEquals(s3iam.get_resource(url), "/path")

    def test_get_resource_with_bucket_host_naked_bucket(self):
        url = "http://bucket.s3.amazonaws.com/"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), 'bucket')
        self.assertEquals(s3iam.get_resource(url), "/")

    def test_get_resource_with_bucket_host_naked_bucket(self):
        url = "http://bucket.s3.amazonaws.com"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), 'bucket')
        self.assertEquals(s3iam.get_resource(url), "/")

    def test_get_resource_with_bucket_path_url(self):
        url = "https://s3.amazonaws.com/bucket/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertEquals(s3iam.get_resource(url), "/bucket/path")

    def test_get_resource_with_bucket_path_url_double_bucket(self):
        url = "https://s3.amazonaws.com/bucket/bucket/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertEquals(s3iam.get_resource(url), "/bucket/bucket/path")

    def test_get_resource_with_bucket_path_url_ending_with_slash(self):
        url = "https://s3.amazonaws.com/bucket/bucket/path/"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertEquals(s3iam.get_resource(url), "/bucket/bucket/path")

    def test_get_resource_with_bucket_path_url_ending_with_slash(self):
        url = "https://s3.amazonaws.com/bucket/"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertEquals(s3iam.get_resource(url), "/bucket/")

    def test_get_resource_with_bucket_path_url_no_bucket(self):
        url = "https://s3.amazonaws.com/path"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertRaises(RuntimeError, s3iam.get_resource, url)

    def test_get_resource_with_bucket_path_url_no_path(self):
        url = "https://s3.amazonaws.com"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertRaises(RuntimeError, s3iam.get_resource, url)

    def test_get_resource_with_bucket_path_url_no_path_slash(self):
        url = "https://s3.amazonaws.com/"
        self.assertEquals(s3iam.get_hostname_embedded_bucket(url), None)
        self.assertRaises(RuntimeError, s3iam.get_resource, url)


class CountingLogger(object):
    """
    Logger with message counter
    """
    counter = {}

    @classmethod
    def log(cls, level, message):
        key = "%s_%s" % (level, message,)
        if cls.counter.get(key):
            cls.counter[key] += 1
        else:
            cls.counter[key] = 1

    @classmethod
    def reset(cls):
        cls.counter = {}


class Repo(object):
    """
    Fake Repository
    Very loosely based on yum.yumRepos.YumRepository
    """
    def __init__(self, repoid):
        self.baseurl = []
        self.id = repoid

    def __getattr__(self, name):
        """ default arguments handler """
        return None

    def baseurlAdd(self, baseurl):
        """
        baseurl is normally setup from mirrorlist
        S3 plugin does not handle mirrorlist
        """
        self.baseurl.append(baseurl)


class S3GrabberTest(unittest.TestCase):

    def test_sign_example_url(self):
        """
        Verify the signing alghoritm
        """
        fakerepo = Repo('fakerepo')
        fakerepo.baseurlAdd("http://fakerepo.s3.amazonaws.com/")
        grabber = s3iam.S3Grabber(fakerepo)
        grabber.access_key = "AKIAIOSFODNN7EXAMPLE"
        grabber.secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        grabber.token = 'None'
        request = grabber._request("photos/puppy.jpg")
        signature = grabber.sign(request,
                                 timeval=(2013, 1, 1, 0, 0, 0, 0, 0, 0))
        self.assertEqual(signature.strip(), "WMjyjyTNSM6359fP19vZtbxjykY=")

    def test_init_with_many_baseurl_should_raise_error(self):
        """
        Only 1 baseurl is currently supported
        """
        fakerepo = Repo('fakerepo')
        fakerepo.baseurlAdd("http://bucket1.s3.amazonaws.com/")
        fakerepo.baseurlAdd("http://bucket2.s3.amazonaws.com/")
        self.assertRaises(yum.plugins.PluginYumExit, s3iam.S3Grabber, fakerepo)


if __name__ == '__main__':
    unittest.main()
