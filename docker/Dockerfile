########################################
##         CREATE BASE IMAGE          ##
########################################
FROM ubuntu:22.04 AS base

SHELL ["/bin/bash", "-o", "pipefail", "-o", "errexit", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN echo 'debconf debconf/frontend select Noninteractive' | debconf-set-selections

# Dependencies from apt-requirements.txt
COPY docker/apt-requirements.txt /apt-requirements.txt
# hadolint ignore=SC2046
RUN apt-get update && \
    apt-get install -y --no-install-recommends $(grep -v '^#' /apt-requirements.txt | tr '\n' ' ') && \
    rm -rf /var/lib/apt/lists/* /apt-requirements.txt

# Python dependencies
COPY docker/python-requirements.txt /python-requirements.txt
RUN pip3 install --no-cache-dir -r /python-requirements.txt && rm /python-requirements.txt

# Add user and scripts dir (mounted as volume at run time)
ENV USER=ubuntu
RUN groupadd -g 1000 ${USER} && \
    useradd -m -u 1000 -g ${USER} ${USER} && \
    mkdir -p /home/${USER}/scripts && \
    chown -R ${USER}:${USER} /home/${USER}/scripts && \
    # Passwordless sudo for PX4 ubuntu.sh (runs in non-interactive Docker build)
    echo "${USER} ALL=(ALL) NOPASSWD:ALL" >> /etc/sudoers.d/${USER} && \
    chmod 0440 /etc/sudoers.d/${USER}

########################################
##              BUILD PX4             ##
########################################

FROM base AS build-px4

ARG PX4_VERSION=v1.16.0

COPY docker/rcS.patch /tmp/rcS.patch

# Reduce git clone failures on flaky networks (buffer + retry)
RUN git config --global http.postBuffer 524288000 && \
    git config --global http.lowSpeedLimit 0 && \
    git config --global http.lowSpeedTime 999999

USER ${USER}
RUN for i in 1 2 3; do git clone --recurse-submodules -b ${PX4_VERSION} https://github.com/PX4/PX4-Autopilot.git /home/${USER}/PX4-Autopilot && break || { rm -rf /home/${USER}/PX4-Autopilot; sleep 15; }; done && \
    cd /home/${USER}/PX4-Autopilot && \
    git apply /tmp/rcS.patch && \
    ./Tools/setup/ubuntu.sh --no-nuttx && \
    make px4_sitl_default && \
    cd /home/${USER} && \
    mkdir -p px4_sitl/bin px4_sitl/romfs/etc && \
    cp -a PX4-Autopilot/build/px4_sitl_default/bin px4_sitl/ && \
    tar xf PX4-Autopilot/build/px4_sitl_default/romfs_files.tar -C px4_sitl/romfs/etc

########################################
##         FINAL PX4 IMAGE             ##
########################################

FROM build-px4 AS px4

USER ${USER}
WORKDIR /home/${USER}

ENTRYPOINT ["/bin/bash"]
