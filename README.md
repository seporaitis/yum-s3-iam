# yum-s3-iam

This is [Yum](http://yum.baseurl.org/) plugin that allows usage of
private S3 buckets as package repositories. It also uses AWS [Identity
and Access Management](http://aws.amazon.com/iam/) (IAM) roles for authorization, so you do not
need to enter your access/secret key pair anywhere in configuration.

## What is IAM Role?

Roles are permissions that can be assigned to an entity, in this case
an AWS EC2 service. About how it works I suggest you dig through
[docs](http://aws.amazon.com/documentation/iam/).

What is important for us: when you assign role to an EC2 instance,
a constantly rotated (by AWS) access credentials become available for
access within the instance. This means you don't need to store them
anywhere, to change and/or rotate them, and you have a fine-grain
control on what actions can be made using those credentials.

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
