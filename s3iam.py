#!/usr/bin/env python
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

__author__ = "Julius Seporaitis"
__email__ = "julius@seporaitis.net"
__copyright__ = "Copyright 2012, Julius Seporaitis"
__license__ = "Apache 2.0"
__version__ = "1.1.0"

import urllib2
import urlparse
import time
import hashlib
import hmac
import json
import sys
from copy import copy
import re

import yum
import yum.config
import yum.Errors
import yum.plugins
import warnings

from urlgrabber.grabber import URLGrabError
from yum.yumRepo import YumRepository
from yum import logginglevels
import logging


__all__ = ['requires_api_version', 'plugin_type', 'CONDUIT',
           'config_hook', 'prereposetup_hook']

requires_api_version = '2.5'
plugin_type = yum.plugins.TYPE_CORE
CONDUIT = None
DEFAULT_DELAY = 3
DEFAULT_BACKOFF = 2
BUFFER_SIZE = 1024*1024*32
UNSUPPORTED_ATTRIBUTES = ['mirrorlist', 'proxy']

verbose_logger = logging.getLogger("yum.verbose.Repos")
logger = logging.getLogger("yum.Repos")

def config_hook(conduit):
    yum.config.RepoConf.s3_enabled = yum.config.BoolOption(False)
    yum.config.RepoConf.key_id = yum.config.Option()
    yum.config.RepoConf.secret_key = yum.config.Option()
    # Usually this is taken care with urlgrabber but not here
    yum.config.RepoConf.backoff = yum.config.Option()
    yum.config.RepoConf.delay = yum.config.Option()


def prereposetup_hook(conduit):
    """Plugin initialization hook. Setup the S3 repositories."""

    repos = conduit.getRepos()

    for repo in repos.listEnabled():
        if isinstance(repo, YumRepository) and repo.s3_enabled:
            new_repo = S3Repository(repo.id, repo.baseurl)
            new_repo.name = repo.name
            new_repo.basecachedir = repo.basecachedir
            new_repo.gpgcheck = repo.gpgcheck
            new_repo.gpgkey = repo.gpgkey
            new_repo.key_id = repo.key_id
            new_repo.secret_key = repo.secret_key
            new_repo.enablegroups = repo.enablegroups

            # unsupported attributes
            for attr in UNSUPPORTED_ATTRIBUTES:
                if getattr(repo, attr):
                    msg = "%s: Unsupported attribute: %s." % (__file__, attr)
                    raise yum.plugins.PluginYumExit(msg)

            # handling HTTP errors
            new_repo.retries = repo.retries
            new_repo.backoff = repo.backoff
            new_repo.delay = repo.delay

            if hasattr(repo, 'base_persistdir'):
                new_repo.base_persistdir = repo.base_persistdir
            if hasattr(repo, 'metadata_expire'):
                new_repo.metadata_expire = repo.metadata_expire
            if hasattr(repo, 'skip_if_unavailable'):
                new_repo.skip_if_unavailable = repo.skip_if_unavailable
            if hasattr(repo, 'mdpolicy'):
                new_repo.mdpolicy = repo.mdpolicy

            # Per repo cache is implemented in some forks
            # eg. yum-3.4.3-137.51.amzn1.noarch.
            # It never made it mainstream:
            # https://bugzilla.redhat.com/show_bug.cgi?id=1001072
            if hasattr(repo, 'keepcache'):
                new_repo.keepcache = repo.keepcache

            # Requires priority plugin
            if hasattr(repo, 'priority'):
                new_repo.priority = repo.priority

            verbose_logger.log(logginglevels.DEBUG_2, new_repo.dump())
            repos.delete(repo.id)
            repos.add(new_repo)


class S3Repository(YumRepository):
    """Repository object for Amazon S3, using IAM Roles."""

    def __init__(self, repoid, baseurl):
        super(S3Repository, self).__init__(repoid)
        self.iamrole = None
        self.baseurl = baseurl
        self.grabber = None
        self.enable()

    @property
    def grabfunc(self):
        raise NotImplementedError("grabfunc called, when it shouldn't be!")

    @property
    def grab(self):
        if not self.grabber:
            self.grabber = S3Grabber(self)
            if self.key_id and self.secret_key:
                self.grabber.set_credentials(self.key_id, self.secret_key)
            else:
                self.grabber.get_role()
                self.grabber.get_credentials()
        return self.grabber

    def _getFile(self, **kwargs):
        """
            Override _getFile from yumRepo to ignore non-relative urls.
        """
        # Override `url` property of file so `yum` uses rel. paths `relative`
        # Baseurl, specified in `yum.repos.d/somerepo.repo` will be used to
        # form all urls instead of absolute paths.
        # The intent is to use a single retriever for all resources originating
        # from a single repository.
        # The helpful side effect here is that if we specify an `https://` in
        # baseurl in `yum.repos.d`, then that `https` setting will be passed
        # through metadata and package downloads.
        # On the downside, you cannot specify an alternate server for
        # downloading packages.
        # LOC: http://yum.baseurl.org/gitweb?p=yum.git;a=blob;f=yum/yumRepo.py;h=f7257d1c1ccb743fbc2ffb5611596698137387b5;hb=HEAD#l741
        # sample sequence of requests:
        # metadata (repomd.xml) => sqlite DBs => package
        # {'text': 'packages','relative': 'repodata/repomd.xml',
        # 'local': '/var/cache/yum/x86_64/2014.03/packages/repomdEd8Yujtmp.xml', 'size': 102400}
        # {'text': 'packages/primary_db', 'reget': None,
        # 'relative': 'repodata/primary.1456367509.sqlite.bz2',
        # 'local': '/var/cache/yum/x86_64/2014.03/packages/primary.1456367509.sqlite.bz2', 'size': None}
        # {'url': 'http://packages.s3.amazonaws.com/cent6',
        # 'text': 'sysdig-0.5.0-x86_64.rpm','relative': 'RPMS/sysdig-0.5.0-x86_64.rpm',
        # 'local': '/var/cache/yum/x86_64/2014.03/packages/packages/sysdig-0.5.0-x86_64.rpm', 'size': 1764624}
        #
        # package has a url property that allow downloads from sources that are
        # hosted on other servers than metadata. Different urlgrabber is
        # instantiated.
        # Overriding url property enforces usage of relative urls and thus
        # single urlgrabber is used.

        # Convert all package urls to relative
        if kwargs.get('url'):
            kwargs['url'] = None

        return super(S3Repository, self)._getFile(**kwargs)


class S3Grabber(object):

    def __init__(self, repo):
        """
        Initialize file grabber.
        Note: Currently supports only single repo.baseurl.
              Only the first item of the list will be used.
        """

        if len(repo.baseurl) != 1:
            msg = "%s: repository '%s' must" % (__file__, repo.id, )
            msg += 'have only one baseurl value'
            raise yum.plugins.PluginYumExit(msg)
        else:
            self.baseurl = repo.baseurl[0]

        self.retries = repo.retries

        if repo.backoff is None:
            self.backoff = DEFAULT_BACKOFF
        else:
            self.backoff = repo.backoff

        if repo.delay is None:
            self.delay = DEFAULT_DELAY
        else:
            self.delay = repo.delay

        # Ensure urljoin doesn't ignore base path:
        if not self.baseurl.endswith('/'):
            self.baseurl += '/'

    def get_role(self):
        """
        Read IAM role from AWS metadata store.
        """
        request = urllib2.Request(
            urlparse.urljoin(
                "http://169.254.169.254",
                "/latest/meta-data/iam/security-credentials/"
            ))

        response = None
        try:
            response = urllib2.urlopen(request)
            self.iamrole = (response.read())
        finally:
            if response:
                response.close()

    def get_credentials(self):
        """Read IAM credentials from AWS metadata store.
        Note: This method should be explicitly called after constructing new
              object, as in 'explicit is better than implicit'.
        """
        url = urlparse.urljoin(
            urlparse.urljoin(
                "http://169.254.169.254/",
                "latest/meta-data/iam/security-credentials/",
            ), self.iamrole)

        request = urllib2.Request(url)
        response = None

        try:
            response = urllib2.urlopen(request)
            data = json.loads(response.read())
            verbose_logger.log(logginglevels.DEBUG_2,
                               "Successfully retrieved IAM credentials")
        finally:
            if response:
                response.close()

        self.access_key = data['AccessKeyId']
        self.secret_key = data['SecretAccessKey']
        self.token = data['Token']

    def set_credentials(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key
        self.token = None

    def _request(self, path):
        url = urlparse.urljoin(self.baseurl, urllib2.quote(path))
        request = urllib2.Request(url)
        if self.token:
            request.add_header('x-amz-security-token', self.token)
        signature = self.sign(request)
        request.add_header('Authorization', "AWS {0}:{1}".format(
            self.access_key,
            signature))
        return request

    def urlgrab(self, url, filename=None, **kwargs):
        """
        grab the file at <url> and make a local copy at <filename>
        If filename is None, the basename of the url is used.
        """

        parts = urlparse.urlparse(url)
        (scheme, host, path, parm, query, frag) = parts
        if filename is None:
            filename = os.path.basename(urllib.unquote(path))

        response = None
        retries = copy(self.retries)
        delay = self.delay

        out = open(filename, 'w+')
        while True:
            try:
                request = self._request(url)
                logger.log(logginglevels.DEBUG_2, "GET: %s" % url)
                response = urllib2.urlopen(request)
                buff = response.read(BUFFER_SIZE)
                while buff:
                    out.write(buff)
                    buff = response.read(BUFFER_SIZE)

            except urllib2.HTTPError, e:
                if retries > 0:
                    retries -= 1
                    msg = "%s, Retry attempt %d in %d seconds..." % \
                        (str(e), self.retries-retries, delay)
                    verbose_logger.log(logginglevels.DEBUG_2, msg)
                    time.sleep(delay)
                    delay *= self.backoff
                else:
                    # Wrap exception as URLGrabError so that YumRepository
                    # catches it
                    msg = '%s on %s tried %s time(s)' % \
                        (e, url, self.retries)

                    new_e = URLGrabError(14, msg)
                    new_e.code = e.code
                    new_e.exception = e
                    new_e.url = url
                    raise new_e

            finally:
                if response:
                    response.close()
                    break

            out.close()
            sys.stdout.flush()
        return filename

    def urlopen(self, url, **kwargs):
        """urlopen(url) open the remote file and return a file object."""
        return urllib2.urlopen(self._request(url))

    def urlread(self, url, limit=None, **kwargs):
        """urlread(url) return the contents of the file as a string."""
        return urllib2.urlopen(self._request(url)).read()

    def sign(self, request, timeval=None):
        """Attach a valid S3 signature to request.
        request - instance of Request
        """
        date = time.strftime("%a, %d %b %Y %H:%M:%S GMT",
                             timeval or time.gmtime())
        request.add_header('Date', date)
        host = request.get_host()

        try:
            resource = get_resource(request.get_full_url())
        except RuntimeError, e:
            logger.log(logginglevels.DEBUG_4, e.msg)
            msg = "Unable to resolve bucket from: %s." % request.get_full_url()
            msg += "Please use http(s)://bucket.s3.amazonaws.com/path or "
            msg += "http(s)://s3.amazonaws.com/bucket/path as baseurl"
            raise yum.plugins.PluginYumExit(msg)

        # For dynamic IAM credentials token is retrieved from metadata endpoint
        # It's is not required for static IAM credentials
        if self.token:
            amz_headers = 'x-amz-security-token:%s\n' % self.token
        else:
            amz_headers = ''

        sigstring = ("%(method)s\n\n\n%(date)s\n"
                     "%(canon_amzn_headers)s%(canon_amzn_resource)s") % ({
                         'method': request.get_method(),
                         'date': request.headers.get('Date'),
                         'canon_amzn_headers': amz_headers,
                         'canon_amzn_resource': resource})
        digest = hmac.new(
            str(self.secret_key),
            str(sigstring),
            hashlib.sha1).digest()
        signature = digest.encode('base64')
        return signature.strip()


def get_hostname_embedded_bucket(url):
    """
        Extracts bucket from the URL
    """
    # find rightmost s3.*amazonaws.com and strip it to get bucket
    parsed = urlparse.urlparse(url)
    bucket = None
    match = re.search(r'(\.[\w-]+?\.amazonaws\.com)',
                      parsed.netloc)
    if match:
        # strip s3.*amazonaws.com and return bucket
        bucket = parsed.netloc.replace(match.group(0), '')

    return bucket


def get_resource(url):
    """
        Extracts resource information from the URL
    """
    hostname_embedded_bucket = get_hostname_embedded_bucket(url)
    parsed = urlparse.urlparse(url)

    if hostname_embedded_bucket:
        verbose_logger.log(logginglevels.DEBUG_4,
                           "Found bucket:%s" % hostname_embedded_bucket)
        result = parsed.path
        if not result:
            result = "/"
    else:
        if parsed.path.count('/') < 2:
            verbose_logger.log(logginglevels.DEBUG_4,
                               "Found resource: %s" % parsed.path)
            # http://s3.amazonaws.com/path is invalid since it does not have
            # bucket in the path
            msg = "Could not determine valid s3 bucket %s" % url
            raise RuntimeError(msg)
        result = parsed.path

    return result
