FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc-arm-linux-gnueabihf binutils-arm-linux-gnueabihf libc6-dev-armhf-cross \
    bc bison flex libssl-dev libelf-dev device-tree-compiler cpio \
    xz-utils bzip2 python3 ca-certificates patch git rsync kmod \
    dropbear-bin openssh-client \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /work
