# yum-s3-iam

This is [Yum](http://yum.baseurl.org/) plugin that lets you use
private S3 buckets as package repositories. Plugin uses AWS
[Identity and Access Management](http://aws.amazon.com/iam/) (IAM)
roles for authorization, so you do not need to enter your
access/secret key pair anywhere in configuration.

## What is IAM Role?

Roles can be assumed by AWS EC2 instances to gain special
permissions. About how it works I suggest you dig through
[docs](http://aws.amazon.com/documentation/iam/).

What is important for us: when you assign role to an EC2 instance,
a constantly rotated (by AWS) access credentials become available for
access within the instance. This means you don't need to store them
anywhere, to change and/or rotate them, and you have a fine-grain
control on what actions can be made using those credentials.

## How-to set it up?

See a great blog post by Jeremy Carroll which explains how to use this
plugin in depth: [S3 Yum Repos With IAM Authorization](http://www.carrollops.com/blog/2012/09/11/s3-yum-repos-with-iam-authorization/).

## What's with the tests?

The tests will fail, except maybe for the aws signature generation
test. And although this code successfully runs on a live machine, _I
would like some advice of how I could write tests for Yum plugin/AWS
API consumer like this one_.

## License

Apache 2.0 license. See LICENSE.

## Author(s)

- Julius Seporaitis
- [Robert Melas' code](https://github.com/rmela/yum-s3-plugin/) was
  used as a reference. See NOTICE.
