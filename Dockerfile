FROM  python:3.11-alpine
MAINTAINER Artem Alexandrov <qk4l@tem4uk.ru>
ENV REFRESHED_AT 2024050501
ENV CONFIG_FILE /config.yml
WORKDIR /opt/zabbix-cachet
COPY setup.py .
COPY src/zabbix_cachet ./src/zabbix_cachet
RUN pip3 install -e .

CMD ["python", "/opt/zabbix-cachet/src/zabbix_cachet/main.py"]

