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
sys.path.append('.')
import s3iam


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
