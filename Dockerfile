FROM cseelye/ubuntu-nginx-base


RUN apt-get update && \
    apt-get --assume-yes upgrade && \
    apt-get --assume-yes install curl python-dev build-essential python3

RUN apt-get --assume-yes install python3-pip
RUN apt-get --assume-yes install python3-setuptools
RUN apt-get --assume-yes install uwsgi uwsgi-plugin-python3 nginx-full

COPY ./requirements.txt /
RUN pip3 install --upgrade pip
RUN pip3 install --requirement /requirements.txt

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY uwsgi-common.ini /etc/uwsgi/uwsgi-common.ini
COPY nginx.conf /etc/nginx/
COPY app.conf /etc/nginx/conf.d/app.conf
COPY app /app

WORKDIR /app
CMD ["/usr/bin/supervisord"]