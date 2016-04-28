# yum-s3-iam

This is a [yum](http://yum.baseurl.org/) plugin that allows for
private AWS S3 buckets to be used as package repositories. The plugin
utilizes AWS [Identity and Access Management](http://aws.amazon.com/iam/)
(IAM) roles for authorization, removing any requirement for an access or
secret key pair to be defined anywhere in your repository configuration.

## What is an IAM Role?

IAM Roles are used to control access to AWS services and resources.

For further details, take a look at the AWS-provided documentation:
[docs](http://aws.amazon.com/documentation/iam/).

Why it's useful: when you assign an IAM role to an EC2 instance,
credentials to access the instance are automatically provided by AWS.
This removes the need to store them, change and/or rotate
them, while also providing fine-grain controls over what actions can
be performed when using the credentials.

This particular plug-in makes use of the IAM credentials when accessing
S3 buckets backing a yum repository.

## How to set it up?

There is a great blog post by Jeremy Carroll which explains in depth how to
use this plugin:
[S3 Yum Repos With IAM Authorization](http://www.carrollops.com/blog/2012/09/11/s3-yum-repos-with-iam-authorization/).

## Testing

### Unit testing
* Use `make test` to run some simple tests.

### Integration Testing (with Docker)

The test is run in the containerized environment, based on [centos:6](https://hub.docker.com/_/centos/) Docker image.
* The usual pre-requisites are necessary to configure docker runtime and they're not covered here.
Make sure you can run `docker ps` successfully before starting.
* Use `make dtest` to run integration test in a docker container.
 Sample output:

```
(default) ❯ make dtest
docker build -t pbase/yum-plugin-s3-iam .
Sending build context to Docker daemon 567.3 kB
Step 1 : FROM centos:6
 ---> ed452988fb6e
Step 2 : RUN yum -y install createrepo rpm-build && yum clean all
 ---> Using cache
 ---> ffe4e2c9256f
Step 3 : WORKDIR /tmp/
 ---> Using cache
 ---> f7e45933a0f8
Step 4 : ADD . /tmp/
 ---> df825cd111c7
Removing intermediate container 4a52af4336e7
Step 5 : ADD tests.py /tmp/s3iam_tests.py
 ---> 13e5ec064062
Removing intermediate container 86ecb5cb7478
Step 6 : RUN make rpm
 ---> Running in 8d70496f764d
 ---> 76d497363a83
Removing intermediate container 8d70496f764d
Step 7 : RUN echo $REPO > /etc/yum.repos.d/s3iam.repo
 ---> Running in d494f22a7d11
 ...
 ---> f18f8c10b97f
Removing intermediate container d494f22a7d11
Step 8 : CMD python /tmp/s3iam_tests.py
 ---> Running in d87f96a3f19b
 ---> 309c415ce206
Removing intermediate container d87f96a3f19b
Successfully built 309c415ce206
docker run pbase/yum-plugin-s3-iam:latest
........................
----------------------------------------------------------------------
Ran 24 tests in 4.138s

OK

```

Please see [Dockerfile](./Dockerfile) for more information

## License

Apache 2.0 license. See LICENSE.

## Maintainers

- Mathias Brossard
- Mischa Spiegelmock
- Sean Edge
- [Michal Bicz](https://github.com/bemehow)

## Author(s)

- Julius Seporaitis
- [Robert Melas' code](https://github.com/rmela/yum-s3-plugin/) was
  used as a reference. See NOTICE.
