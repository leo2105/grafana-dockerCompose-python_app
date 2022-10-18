FROM ubuntu:18.04
ENV TZ=America/Bahia
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone
RUN apt-get update && apt-get install -yqq supervisor vim openssh-server ssh iputils-ping build-essential tzdata tree
RUN apt -y install python3.8-dev python3.8-distutils
RUN wget https://bootstrap.pypa.io/get-pip.py
RUN python3.8 get-pip.py

RUN apt-get install -yqq freetds-bin ldap-utils libffi6 libsasl2-2 libsasl2-modules libssl1.1 locales lsb-release sasl2-bin sqlite3 unixodbc virtualenv zip unzip git
RUN apt-get upgrade -yqq 
RUN apt-get -y install libgl1
COPY requirements.txt requirements.txt
RUN pip3.8 install -r requirements.txt

WORKDIR /app