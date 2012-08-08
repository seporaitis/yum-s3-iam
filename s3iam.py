"""
Yum plugin for Amazon S3 access using IAM roles.

This plugin provides access to a protected Amazon S3 bucket using Amazon REST
authentication scheme.

Install:
1. Copy this file to /usr/lib/yum-plugins/
2. Copy s3iam.conf file to /etc/yum/pluginconf.d/
3. Configure your S3 repository as in example s3iam.repo

Note: this will work only on Amazon EC2 machine that has a role assigned to it.
So, do not forget to do that.

Credits:
This code is based on yum-s3-plugin[1] by rmela.

[1]: https://github.com/rmela/yum-s3-plugin/
"""
#   Copyright 2012, Julius Seporaitis
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import os
import sys
import urllib2
import time
import hashlib
import hmac
import base64
import json

from yum.plugins import TYPE_CORE
from yum.yumRepo import YumRepository
from yum import config

import yum.Errors


requires_api_version = '2.5'
plugin_type = TYPE_CORE
CONDUIT = None


def config_hook(conduit):
    config.RepoConf.iamrole = config.Option('')

def init_hook(conduit):
    """
    Setup the S3 repositories.
    """

    repos = conduit.getRepos()
    for key, repo in repos.repos.iteritems():
        if isinstance(repo, YumRepository) and repo.iamrole:
            print "s3iam: found S3 private repository"
            new_repo = S3Repository(key, repo.iamrole)
            new_repo.iamrole = repo.iamrole
            new_repo.baseurl = repo.baseurl
            new_repo.mirrorlist = repo.mirrorlist
            new_repo.basecachedir = repo.basecachedir
            new_repo.gpgcheck = repo.gpgcheck
            new_repo.proxy = repo.proxy
            new_repo.enablegroups = repo.enablegroups
            del repos.repos[repo.id]
            repos.add(new_repo)


class S3Repository(YumRepository):
    """
    Repository object for Amazon S3, using IAM Roles.
    """

    def __init__(self, repoid, iamrole):
        YumRepository.__init__(self, repoid)
        self.iamrole = iamrole
        self.enable()
        self.grabber = None

    def setupGrab(self):
        super(S3Repository, self).setupGrab(self)
        self.grabber = S3Grabber(iamrole=self.iamrole)

    def _getgrabfunc(self):
        raise Exception("get grabfunc called, when it shouldn't be!")

    def _getgrab(self):
        if not self.grabber:
            self.grabber = S3Grabber(baseurl=self.baseurl, iamrole=self.iamrole)
        return self.grabber

    grabfunc = property(lambda self: self.getgrabfunc())
    grab = property(lambda self: self._getgrab())


class S3Grabber(object):

    def __init__(self, baseurl, iamrole):
        try:
            baseurl = baseurl[0]
        except:
            pass
        self.baseurl = baseurl
        self.iamrole = iamrole

        key, secret, token = S3Grabber.get_credentials(self.iamrole)
        self.access_key = key
        self.secret_key = secret
        self.token = token

    def _request(self, url):
        req = urllib2.Request("%s%s" % (self.baseurl, url))
        req.add_header('x-amz-security-token', self.token)
        S3Grabber.sign(req, self.access_key, self.secret_key, self.token)
        return req

    def urlgrab(self, url, filename=None, **kwargs):
        """urlgrab(url) copy the file to the local filesystem."""
        req = self._request(url)
        if not filename:
            filename = req.get_selector()
            if filename.startswith('/'):
                filename = filename[1:]
        out = open(filename, 'w+')
        resp = urllib2.urlopen(req)
        buff = resp.read(8192)
        while buff:
            out.write(buff)
            buff = resp.read(8192)

        return filename

    def urlopen(self, url, **kwargs):
        """urlopen(url) open the remote file and return a file object."""
        return urllib2.urlopen(self._request(url))

    def urlread(self, url, limit=None, **kwargs):
        """urlread(url) return the contents of the file as a string."""
        return urllib2.urlopen(self._request(url)).read()

    @classmethod
    def sign(cls, request, access_key, secret_key, token, date=None):
        """Attach a valid S3 signature to request."""
        date = time.strftime("%a, %d %b %Y %H:%M:%S +0000", date or time.gmtime())
        request.add_header('Date', date)
        host = request.get_host()
        pos = host.find(".s3")
        bucket = host[:pos]
        resource = "/%s%s" % (bucket, request.get_selector(), )
        amz_headers = 'x-amz-security-token:%s\n' % (token, )
        sigstring = """%(method)s\n\n\n%(date)s\n%(canon_amzn_headers)s%(canon_amzn_resource)s""" % ({
            'method': request.get_method(),
            'date': request.headers.get('Date'),
            'canon_amzn_headers': amz_headers,
            'canon_amzn_resource': resource})
        digest = hmac.new(str(secret_key), str(sigstring), hashlib.sha1).digest()
        signature = base64.b64encode(digest)
        request.add_header('Authorization', "AWS %s:%s" % (access_key, signature))

    @classmethod
    def get_credentials(cls, role):
        """Read IAM role credentials from metadata store."""
        print "s3iam: retrieving credentials for IAM role '%s'" % (role, )
        req = urllib2.Request("http://169.254.169.254/latest/meta-data/iam/security-credentials/%s" % (role, ))
        res = urllib2.urlopen(req)
        data = json.loads(res.read())
        access_key = data['AccessKeyId']
        secret_key = data['SecretAccessKey']
        token = data['Token']
        return access_key, secret_key, token
