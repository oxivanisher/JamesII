FROM python:2

WORKDIR /usr/src/app
RUN mkdir -p /usr/src/app/config
VOLUME /usr/src/app/config

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src .
COPY config .

CMD [ "python", "./james.py" ]