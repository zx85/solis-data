FROM python:3.12.2-alpine

# Copy script which should be run
COPY ./scripts/* /usr/local/scripts/
COPY ./requirements.txt /

RUN chmod -R 755 /usr/local/scripts

# add all the shizzle
RUN apk update && apk add --no-cache bash busybox-openrc coreutils gcc musl-dev libffi-dev

# pip requirements
RUN pip install -r requirements.txt

# Run the cron every minute
ADD ./crontab.txt /crontab.txt
RUN /usr/bin/crontab /crontab.txt

CMD ["/usr/local/scripts/runcron.sh"]
