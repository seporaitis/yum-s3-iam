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
import unittest
import os
import os.path
import urllib2
import time
sys.path.append('.')
import s3iam

from urlparse import urlparse


class S3GrabberTest(unittest.TestCase):

    def test_example_sign(self):
        """Test with example data"""
        req = urllib2.Request("https://johnsmith.s3.amazonaws.com/photos/puppy.jpg")
        grabber = s3iam.S3Grabber("http://johnsmith.s3.amazonaws.com/", iamrole="s3access")
        grabber.access_key = "AKIAIOSFODNN7EXAMPLE"
        grabber.secret_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        grabber.token = None
        request = grabber._request("photos/puppy.jpg")
        signature = grabber.sign(request, timeval=time.mktime(time.struct_time(
            tm_year=2007,
            tm_mon=3,
            tm_mday=27,
            tm_hour=19,
            tm_min=36,
            tm_sec=42)))
        self.assertEqual(signature, "bWq2s1WEIj+Ydj0vQ697zp+IXMU=")


if __name__ == '__main__':
    unittest.main()
