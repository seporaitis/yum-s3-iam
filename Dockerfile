FROM amazonlinux:2

RUN mkdir -p /app

RUN yum update -y                                                               \
    &&                                                                          \
    yum install -y                                                              \
        # Source Control                                                        \
        git                                                                     \
        # RPM build tools                                                       \
        rpm-build createrepo                                                    \
        # Basics                                                                \
        which python2-pip zip jq make rsync python2-mock                        \
    &&                                                                          \
    pip install --upgrade pip                                                   \
    &&                                                                          \
    # AWS CLI                                                                   \
    pip install awscli

ADD . /app
WORKDIR /app
ENTRYPOINT ["/usr/bin/make"]
