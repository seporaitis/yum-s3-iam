"""
Tests currently focus on REST request signing and urlgrabber.

In order to run tests you need to:
1. create a test_values.py file with required information (see try:except: below)
2. execute them on an Amazon EC2 machine with assigned IAM role.
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

import sys
import unittest
import os
import os.path
sys.path.append('.')
import s3iam

from urlparse import urlparse


try:
    from test_values import *
except:
    BASE_URL = ""
    BUCKET_NAME = ""
    FILE_PATH = ""
    IAM_ROLE = ""


class S3GrabberTest(unittest.TestCase):

    def setUp(self):
        repository_url = "%s%s/" % (BASE_URL, BUCKET_NAME)
        self.grabber = s3iam.S3Grabber(baseurl=repository_url, role=IAM_ROLE)

    def test_invalid_key(self):
        req = urllib2.Request("%s%s/%s" % (BASE_URL, BUCKET_NAME, FILE_PATH))
        self.grabber.secret_key = "bogus_key"
        self.grabber.sign(req)
        self.assertRaises(urllib2.HTTPError, urllib2.urlopen, req)

    def test_urlgrab(self):
        url = urlparse(TEST_FILE)
        result = self.grabber.urlgrab(TEST_FILE)
        self.assertTrue(os.path.exists)
