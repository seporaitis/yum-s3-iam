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

## Notes on S3 buckets and URLs

There are 2 types of S3 URLs:
- virtual-hosted–style URL:
  - `https://<bucket>.s3.amazonaws.com/<path>` if region is US East (us-east-1)
  - `https://<bucket>.s3-<aws-region>.amazonaws.com/<path>` in other regions
- path-style URLs:
  - `https://s3.amazonaws.com/<bucket>/<path>` if region is US East (us-east-1)
  - `https://s3-<aws-region>.amazonaws.com/<bucket>/<path>` in other regions

When using HTTP/S and a bucket name containing a dot (`.`) you need to
use the path-style URL syntax.

## Use outside of EC2

Some use-cases (Continuous Integration, Docker) involve S3-hosted yum
repositories being accessed from outside EC2. For those cases two
options are available:
- Use AWS API keys in AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (and
  optionally AWS_SESSION_TOKEN) environment variables. Those will be
  used as a fallback if IAM role credentials can not be accessed.
- Defining the environment DISABLE_YUM_S3_IAM to 1 will disable the
  use of the yum-s3-iam plugin. This should be used with S3 bucket IP
  white-listing.

## Limitations

Currently the plugin does not support:
- Proxy server configuration
- Multi-valued baseurl or mirrorlist

## Testing

Use `make test` to run some simple tests.

### Testing with docker compose:

```
docker-compose -f docker-compose.yml run yum-s3-iam test
docker-compose -f docker-compose.yml run yum-s3-iam e2e_local

docker-compose -f docker-compose.yml down --volumes --rmi all
```

### Building rpm
```
make rpm VERSION=${VERSION} RELEASE=${RELEASE:-1}
```
### Building rpm with docker compose
```
docker-compose -f docker-compose.yml run yum-s3-iam rpm VERSION=${VERSION} RELEASE=${RELEASE:-1}
```

### Releasing new version
Use `make release VERSION=${VERSION} RELEASE=${RELEASE:-1} REPO_URL=${REPO_URL:-s3://bv-nexus-public-artifacts/yum-repo/}
` to release new version and upload to rpm repository.
or via Docker-compose:
```
docker-compose -f docker-compose.yml run \ 
    -e AWS_ACCESS_KEY_ID=$(aws --profile default configure get aws_access_key_id) \
    -e AWS_SECRET_ACCESS_KEY=$(aws --profile default configure get aws_secret_access_key) \
    yum-s3-iam release \
        VERSION=${VERSION} \
        RELEASE=${RELEASE:-1} \
        REPO_URL=${REPO_URL:-s3://bv-nexus-public-artifacts/yum-repo/}
```

### Run e2e tests with new released version
```
make e2e_release
```
or via Docker-compose:
```
docker-compose -f docker-compose.yml run yum-s3-iam e2e_release
```
## License

Apache 2.0 license. See LICENSE.

## Maintainers

- Mathias Brossard
- Mischa Spiegelmock
- Sean Edge

## Author(s)

- Julius Seporaitis
- [Robert Melas' code](https://github.com/rmela/yum-s3-plugin/) was
  used as a reference. See NOTICE.
