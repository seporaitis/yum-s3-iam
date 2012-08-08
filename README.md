# yum-s3-iam

This is [Yum](http://yum.baseurl.org/) plugin that allows usage of
private S3 buckets as package repositories. It also uses AWS Identity
and Access Management (IAM) roles for authorization, so you do not
need to enter your access/secret key pair anywhere in configuration.

## How-to set it up?

This is kind of rough description:

1. Create IAM Role (e.g. 'applicationserver') and set a policy that
gives s3:GetObject rights to that role.
2. Launch instances with this role assigned.
3. Inside those instances you can use 'yum-s3-iam' as described in
s3iam.py file.

## What's with the tests?

The tests will fail, except maybe for the aws signature generation
test. And although this code successfully runs on a live machine, _I
would like some advice of how I could write tests Yum pluging/AWS API
consumer_.

## License

Apache 2.0 license. See LICENSE.

## Author(s)

I used Robert Melas' code as a reference. See NOTICE.
