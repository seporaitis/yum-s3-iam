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

import urllib2
import urlparse
import datetime
import time
import hashlib
import hmac
import json
import os
import re

import yum
import yum.config
import yum.Errors
import yum.plugins

from yum.yumRepo import YumRepository

__author__ = "Julius Seporaitis"
__email__ = "julius@seporaitis.net"
__copyright__ = "Copyright 2012, Julius Seporaitis"
__license__ = "Apache 2.0"
__version__ = "1.2.1"


__all__ = ['requires_api_version', 'plugin_type', 'CONDUIT',
           'config_hook', 'prereposetup_hook']

requires_api_version = '2.5'
plugin_type = yum.plugins.TYPE_CORE
CONDUIT = None
DEFAULT_DELAY = 3
DEFAULT_BACKOFF = 2
BUFFER_SIZE = 1024 * 1024
OPTIONAL_ATTRIBUTES = ['priority', 'base_persistdir', 'metadata_expire',
                       'skip_if_unavailable', 'keepcache', 'priority']
UNSUPPORTED_ATTRIBUTES = ['mirrorlist']


def config_hook(conduit):
    yum.config.RepoConf.s3_enabled = yum.config.BoolOption(False)
    yum.config.RepoConf.region = yum.config.Option()
    yum.config.RepoConf.key_id = yum.config.Option()
    yum.config.RepoConf.secret_key = yum.config.Option()
    yum.config.RepoConf.delegated_role = yum.config.Option()
    yum.config.RepoConf.baseurl = yum.config.UrlListOption(
        schemes=('http', 'https', 's3', 'ftp', 'file')
    )
    yum.config.RepoConf.backoff = yum.config.Option()
    yum.config.RepoConf.delay = yum.config.Option()


def parse_url(url):
    # http://docs.aws.amazon.com/AmazonS3/latest/dev/UsingBucket.html
    url = url[0] if isinstance(url, list) else url

    # http[s]://<bucket>.s3.amazonaws.com
    m = re.match(r'(http|https|s3)://([a-z0-9][a-z0-9-.]{1,61}[a-z0-9])[.]s3[.]amazonaws[.]com(.*)$', url)
    if m:
        return (m.group(2), None, m.group(3))

    # http[s]://<bucket>.s3-<aws-region>.amazonaws.com
    m = re.match(r'(http|https|s3)://([a-z0-9][a-z0-9-.]{1,61}[a-z0-9])[.]s3-([a-z0-9-]+)[.]amazonaws[.]com(.*)$', url)
    if m:
        return (m.group(2), m.group(3), m.group(4))

    # http[s]://s3.amazonaws.com/<bucket>
    m = re.match(r'(http|https|s3)://s3[.]amazonaws[.]com/([a-z0-9][a-z0-9-.]{1,61}[a-z0-9])(.*)$', url)
    if m:
        return (m.group(2), 'us-east-1', m.group(3))

    # http[s]://s3.cn-north-1.amazonaws.com.cn/<bucket>
    m = re.match(r'(http|https|s3)://s3[.]cn-north-1[.]amazonaws[.]com[.]cn/([a-z0-9][a-z0-9-.]{1,61}[a-z0-9])(.*)$', url)
    if m:
        return (m.group(2), 'cn-north-1', m.group(3))

    # http[s]://s3-<region>.amazonaws.com/<bucket>
    m = re.match(r'(http|https|s3)://s3-([a-z0-9-]+)[.]amazonaws[.]com/([a-z0-9][a-z0-9-.]{1,61}[a-z0-9])(.*)$', url)
    if m:
        return (m.group(3), m.group(2), m.group(4))

    return (None, None, None)


def replace_repo(repos, repo):
    repos.delete(repo.id)
    repos.add(S3Repository(repo.id, repo))


def prereposetup_hook(conduit):
    """Plugin initialization hook. Setup the S3 repositories."""

    if 'DISABLE_YUM_S3_IAM' in os.environ and os.environ['DISABLE_YUM_S3_IAM']:
        return

    repos = conduit.getRepos()
    for repo in repos.listEnabled():
        url = repo.baseurl
        if(isinstance(url, list)):
            if len(url) == 0:
                continue
            url = url[0]
        if re.match(r'^s3://', url):
            repo.s3_enabled = 1
        if isinstance(repo, YumRepository) and repo.s3_enabled:
            replace_repo(repos, repo)


class S3Repository(YumRepository):
    """Repository object for Amazon S3, using IAM Roles."""

    def __init__(self, repoid, repo):
        super(S3Repository, self).__init__(repoid)

        bucket, region, path = parse_url(repo.baseurl)

        if bucket is None:
            msg = "s3iam: unable to parse url %s'" % repo.baseurl
            raise yum.plugins.PluginYumExit(msg)

        if region and region != 'us-east-1':
            self.baseurl = "https://s3-%s.amazonaws.com/%s%s" % (region, bucket, path)
            if 'cn-north-1' in region:
                self.baseurl = "https://s3.cn-north-1.amazonaws.com.cn/%s%s" % (bucket, path)
        else:
            self.baseurl = "https://%s.s3.amazonaws.com%s" % (bucket, path)

        self.name = repo.name
        self.region = repo.region if repo.region else region
        self.basecachedir = repo.basecachedir
        self.gpgcheck = repo.gpgcheck
        self.gpgkey = repo.gpgkey
        self.access_id = repo.key_id
        self.secret_key = repo.secret_key
        self.enablegroups = repo.enablegroups
        self.delegated_role = repo.delegated_role

        self.retries = repo.retries
        self.backoff = repo.backoff
        self.delay = repo.delay

        for attr in OPTIONAL_ATTRIBUTES:
            if hasattr(repo, attr):
                setattr(self, attr, getattr(repo, attr))

        for attr in UNSUPPORTED_ATTRIBUTES:
            if getattr(repo, attr):
                msg = "%s: Unsupported attribute: %s." % (__file__, attr)
                raise yum.plugins.PluginYumExit(msg)

        proxy_config = {}
        if 'https_proxy' in os.environ:
            proxy_config['https'] = os.environ['https_proxy']
        if 'http_proxy' in os.environ:
            proxy_config['http'] = os.environ['http_proxy']
        if repo.proxy:
            proxy_config['https'] = proxy_config['http'] = repo.proxy
        if proxy_config:
            proxy = urllib2.ProxyHandler(proxy_config)
            opener = urllib2.build_opener(proxy)
            urllib2.install_opener(opener)

        self.iamrole = None
        self.grabber = None
        self.enable()

    @property
    def grabfunc(self):
        raise NotImplementedError("grabfunc called, when it shouldn't be!")

    @property
    def grab(self):
        if not self.grabber:
            self.grabber = S3Grabber(self)
            if self.access_id and self.secret_key:
                self.grabber.set_credentials(self.access_id, self.secret_key)
            elif self.delegated_role:
                self.grabber.get_delegated_role_credentials(self.delegated_role)
            else:
                self.grabber.get_role()
                self.grabber.get_credentials()
        return self.grabber


class S3Grabber(object):

    def __init__(self, repo):
        """Initialize file grabber.
        Note: currently supports only single repo.baseurl. So in case of a list
              only the first item will be used.
        """
        if isinstance(repo, basestring):
            self.baseurl = repo
            self.region = None
            self.retries = 0
        else:
            self.id = repo.id
            self.region = repo.region
            self.retries = repo.retries
            self.backoff = DEFAULT_BACKOFF if repo.backoff is None else repo.backoff
            self.delay = DEFAULT_DELAY if repo.delay is None else repo.delay
            if len(repo.baseurl) != 1:
                msg = "%s: repository '%s' must" % (__file__, repo.id)
                msg += 'have only one baseurl value'
                raise yum.plugins.PluginYumExit(msg)
            else:
                self.baseurl = repo.baseurl[0]
        # Ensure urljoin doesn't ignore base path:
        if not self.baseurl.endswith('/'):
            self.baseurl += '/'
        self.access_key = None
        self.secret_key = None
        self.token = None

    def get_role(self):
        """Read IAM role from AWS metadata store."""
        request = urllib2.Request(
            urlparse.urljoin(
                "http://169.254.169.254",
                "/latest/meta-data/iam/security-credentials/"
            ))

        try:
            response = urllib2.urlopen(request)
            self.iamrole = (response.read())
        except Exception:
            response = None
            self.iamrole = ""
        finally:
            if response:
                response.close()

    def get_credentials(self):
        """Read IAM credentials from AWS metadata store.
        Note: This method should be explicitly called after constructing new
              object, as in 'explicit is better than implicit'.
        """
        request = urllib2.Request(
            urlparse.urljoin(
                urlparse.urljoin(
                    "http://169.254.169.254/",
                    "latest/meta-data/iam/security-credentials/",
                ), self.iamrole))

        try:
            response = urllib2.urlopen(request)
            data = json.loads(response.read())
            self.access_key = data['AccessKeyId']
            self.secret_key = data['SecretAccessKey']
            self.token = data['Token']
        except Exception:
            response = None
        finally:
            if response:
                response.close()

        if self.access_key is None and self.secret_key is None:
            if "AWS_ACCESS_KEY_ID" in os.environ:
                self.access_key = os.environ['AWS_ACCESS_KEY_ID']
            if "AWS_SECRET_ACCESS_KEY" in os.environ:
                self.secret_key = os.environ['AWS_SECRET_ACCESS_KEY']
            if "AWS_SESSION_TOKEN" in os.environ:
                self.token = os.environ['AWS_SESSION_TOKEN']

        if self.access_key is None and self.secret_key is None:
            if hasattr(self, 'name'):
                msg = "Could not access AWS credentials, skipping repository '%s'" % (self.name)
            else:
                msg = "Could not access AWS credentials"
            print msg
            from urlgrabber.grabber import URLGrabError
            raise URLGrabError(7, msg)

    def set_credentials(self, access_key, secret_key):
        self.access_key = access_key
        self.secret_key = secret_key
        self.token = None

    def get_delegated_role_credentials(self, delegated_role):
        """Collect temporary credentials from AWS STS service. Uses
        delegated_role value from configuration.
        Note: This method should be explicitly called after constructing new
              object, as in 'explicit is better than implicit'.
        """
        import boto.sts

        sts_conn = boto.sts.connect_to_region(self.get_instance_region())
        assumed_role = sts_conn.assume_role(delegated_role, 'yum')

        self.access_key = assumed_role.credentials.access_key
        self.secret_key = assumed_role.credentials.secret_key
        self.token = assumed_role.credentials.session_token

    def get_instance_region(self):
        """Read region from AWS metadata store."""
        request = urllib2.Request(
            urlparse.urljoin(
                "http://169.254.169.254",
                "/latest/meta-data/placement/availability-zone"
            ))

        response = None
        try:
            response = urllib2.urlopen(request)
            data = response.read()
        finally:
            if response:
                response.close()
        return data[:-1]

    def _request(self, path, timeval=None):
        url = urlparse.urljoin(self.baseurl, urllib2.quote(path))
        request = urllib2.Request(url)
        if self.region:
            self.signV4(request, timeval)
        else:
            self.signV2(request, timeval)
        return request

    def urlgrab(self, url, filename=None, **kwargs):
        """urlgrab(url) copy the file to the local filesystem."""
        request = self._request(url)
        if filename is None:
            filename = request.get_selector()
            if filename.startswith('/'):
                filename = filename[1:]

        response = None
        retries = self.retries
        delay = self.delay
        out = open(filename, 'w+')
        while retries > 0:
            try:
                response = urllib2.urlopen(request)
                buff = response.read(BUFFER_SIZE)
                while buff:
                    out.write(buff)
                    buff = response.read(BUFFER_SIZE)
            except urllib2.HTTPError, e:
                if retries > 0:
                    time.sleep(delay)
                    delay *= self.backoff
                else:
                    # Wrap exception as URLGrabError so that YumRepository catches it
                    from urlgrabber.grabber import URLGrabError
                    msg = '%s on %s tried' % (e, url)
                    if self.retries > 0:
                        msg += ' tried %d time(s)' % (self.retries)
                        new_e = URLGrabError(14, msg)
                        new_e.code = e.code
                        new_e.exception = e
                        new_e.url = url
                        raise new_e
            finally:
                retries -= 1
                if response:
                    response.close()
                    break

        out.close()
        return filename

    def urlopen(self, url, **kwargs):
        """urlopen(url) open the remote file and return a file object."""
        return urllib2.urlopen(self._request(url))

    def urlread(self, url, limit=None, **kwargs):
        """urlread(url) return the contents of the file as a string."""
        return urllib2.urlopen(self._request(url)).read()

    def signV2(self, request, timeval=None):
        """Attach a valid S3 signature to request.
        request - instance of Request
        """
        t = timeval or time.gmtime()
        date = time.strftime("%a, %d %b %Y %H:%M:%S +0000", t)
        request.add_header('Date', date)

        (bucket, ignore, path) = parse_url(request.get_full_url())
        resource = '/' + bucket + path
        if self.token:
            amz_headers = 'x-amz-security-token:%s\n' % self.token
            request.add_header('x-amz-security-token', self.token)
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
        signature = digest.encode('base64').rstrip()

        authorization = "AWS {0}:{1}".format(self.access_key, signature)
        request.add_header('Authorization', authorization)

    def derive(self, key, msg):
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    def deriveKey(self, key, date, region, service):
        kDate = self.derive(('AWS4' + key).encode('utf-8'), date)
        kRegion = self.derive(kDate, region)
        kService = self.derive(kRegion, service)
        return self.derive(kService, 'aws4_request')

    def signV4(self, request, timeval=None):
        algorithm = 'AWS4-HMAC-SHA256'
        t = datetime.datetime.utcnow()

        amzdate = t.strftime('%Y%m%dT%H%M%SZ')
        amz_headers = ('host:%s\nx-amz-date:%s\n' %
                       (request.get_host(), amzdate))
        signed_headers = 'host;x-amz-date'
        if self.token:
            amz_headers += 'x-amz-security-token:%s\n' % self.token
            signed_headers += ';x-amz-security-token'
            request.add_header('x-amz-security-token', self.token)

        # Hash request
        content_h = hashlib.sha256('').hexdigest()  # Empty content
        req = ('GET\n%s\n\n%s\n%s\n%s' %
               (request.get_selector(), amz_headers, signed_headers, content_h))
        req_hash = hashlib.sha256(req).hexdigest()

        # Assemble content to be signed
        datestamp = t.strftime('%Y%m%d')
        scope = datestamp + '/' + self.region + '/s3/aws4_request'
        sign_content = '%s\n%s\n%s\n%s' % (algorithm, amzdate, scope, req_hash)

        # Get derived key
        signing_key = self.deriveKey(self.secret_key, datestamp,
                                     self.region, 's3')

        # Compute signature
        signature = hmac.new(signing_key, (sign_content).encode('utf-8'),
                             hashlib.sha256).hexdigest()

        # Assemble 'Authorization' header value
        credential = self.access_key + '/' + scope
        auth = (('%s Credential=%s, SignedHeaders=%s, Signature=%s') %
                (algorithm, credential, signed_headers, signature))

        request.add_header('x-amz-content-sha256', content_h)
        request.add_header('x-amz-date', amzdate)
        request.add_header('Authorization', auth)
