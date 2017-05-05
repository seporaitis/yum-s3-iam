## 1.2.0 (2017-05-05)
- #48 and #49: Improvements for running outside of EC2 (@mbrossard):
  - Set DISABLE_YUM_S3_IAM environment variable to disable IAM
    authentication, to be used with S3 bucket IP white-listing.
  - Set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY and optionally
    AWS_SESSION_TOKEN environment variables to be used as fallback in
    case IAM roles are not available
- #50: Fix for cross-region STS authentication (@jonnangle)
- #55: Fix for regression on 'us-east-1' (@mestudd, @mbrossard)

## 1.1.2 (2017-02-21)
- #53: Fix for no-region regression introduced by #51 (@mbrossard)

## 1.1.1 (2017-02-16)
- #51: Add support for cn-north-1 region (@mbrossard)

## 1.1.0 (2016-07-11)
- #32: Add support for AWS v4 signature (@mbrossard)
- #32: Add support for s3:// scheme (@asedge, @mbrossard)
- #43: Add retries with exponential back-off (@bemehow, @mbrossard)

## 1.0.3 (2016-07-05)
- #44: Add support for delegated roles (@ToneD)

## 1.0.2 (2015-11-03)
- #34: Fix signature issue with python 2.7 (@mbrossard)
