FROM centos:6

RUN yum -y install createrepo rpm-build && yum clean all

WORKDIR /tmp/

ADD . /tmp/
ADD tests.py /tmp/s3iam_tests.py
RUN make rpm
RUN echo $REPO > /etc/yum.repos.d/s3iam.repo

CMD ["python", "/tmp/s3iam_tests.py"]
