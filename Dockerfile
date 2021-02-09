FROM ubuntu:20.04

LABEL maintainer="Ben Hampson <bjhampson@gmail.com>"

# Set Env vars
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/London
ENV TWS_MAJOR_VRSN=978
ENV IBC_VERSION=3.8.2
ENV IBC_INI=/root/IBController/IBController.ini
ENV IBC_PATH=/opt/IBController
ENV TWS_PATH=/root/Jts
ENV TWS_CONFIG_PATH=/root/Jts
ENV LOG_PATH=/opt/IBController/Logs
ENV JAVA_PATH=/opt/i4j_jres/1.8.0_152-tzdata2019c/bin
ENV APP=GATEWAY

# Install needed packages
RUN apt-get -qq update -y && apt-get -qq install -y unzip xvfb libxtst6 libxrender1 libxi6 socat software-properties-common curl supervisor x11vnc tmpreaper python3-pip openssh-server

# Setup IB TWS
RUN mkdir -p /opt/TWS
WORKDIR /opt/TWS
COPY ./ibgateway-stable-standalone-linux-9782c-x64.sh /opt/TWS/ibgateway-stable-standalone-linux-x64.sh
RUN chmod a+x /opt/TWS/ibgateway-stable-standalone-linux-x64.sh

# Install IBController
RUN mkdir -p /opt/IBController/ && mkdir -p /opt/IBController/Logs
WORKDIR /opt/IBController/
COPY ./IBCLinux-3.8.4-beta.2/  /opt/IBController/
RUN chmod -R u+x *.sh && chmod -R u+x scripts/*.sh

WORKDIR /

# Install TWS
RUN yes n | /opt/TWS/ibgateway-stable-standalone-linux-x64.sh
RUN rm /opt/TWS/ibgateway-stable-standalone-linux-x64.sh

# Must be set after install of IBGateway
ENV DISPLAY :0

# Below files copied during build to enable operation without volume mount
COPY ./ib/IBController.ini /root/IBController/IBController.ini
RUN mkdir -p /root/Jts/
COPY ./ib/jts.ini /root/Jts/jts.ini

# Overwrite vmoptions file
RUN rm -f /root/Jts/ibgateway/978/ibgateway.vmoptions
COPY ./ibgateway.vmoptions /root/Jts/ibgateway/978/ibgateway.vmoptions

# Install Python requirements
RUN pip3 install supervisor

# Setup OpenSSH
RUN mkdir /var/run/sshd
RUN sed -i 's/PermitRootLogin prohibit-password/PermitRootLogin yes/' /etc/ssh/sshd_config
RUN mkdir /root/.ssh
RUN echo "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQDHSnEipi0f0b0YAleafQMHsCdb+Ic9ZB0c4cDh6by2iycWjoDzNDm29fr2tpR4Dvzuc5T/t6RlxUosRaYvyrecjsaAuUWMxkbbM3xcsgMQvTMoBugnfJCObWxj+uOqDSptF/0Tsgi/Jz1pVzovsvb3SJ85Wf/mj45U4MBCynm8cLLxdRhFIoIQ4U6iuI2Ha2IelBlHL5jeTAElLIrU6nksur3hz1pI4DrfBUZUxSSy5jnnWN3OHymx64HCdNyLWchMAM2806f/EBRyHbCMMTci/YKxWHFTENnz96XZxMK5iGJx9soK9dU4EEn7Vv8Eeke0nzqkbs7gM6I3/s5HSx11 bhampson@Bens-MacBook-Air.local" >>/root/.ssh/authorized_keys
RUN chmod 600 /root/.ssh/authorized_keys

# SSH login fix. Otherwise user is kicked off after login
RUN sed 's@session\s*required\s*pam_loginuid.so@session optional pam_loginuid.so@g' -i /etc/pam.d/sshd
RUN sed -ie 's/Port 22/#Port 22/g' /etc/ssh/sshd_config
ENV NOTVISIBLE "in users profile"
RUN echo "export VISIBLE=now" >> /etc/profile

EXPOSE 22

RUN ["/usr/sbin/sshd"]

COPY ./restart-docker-vm.py /root/restart-docker-vm.py

EXPOSE 4004

COPY ./supervisord.conf /root/supervisord.conf

COPY ./root/ /root/

CMD /usr/bin/supervisord -c /root/supervisord.conf
