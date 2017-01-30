FROM  python:3.4-alpine
MAINTAINER Artem Alexandrov <qk4l@tem4uk.ru>
ENV REFRESHED_AT 2017013001
ENV CONFIG_FILE /config.yml
COPY requirements.txt /zabbix-cachet/requirements.txt
COPY zabbix-cachet.py /zabbix-cachet/zabbix-cachet.py
RUN pip3 install -r /zabbix-cachet/requirements.txt
WORKDIR /opt/

CMD ["python", "/zabbix-cachet/zabbix-cachet.py"]

