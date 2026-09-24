#!/bin/bash
set -euo pipefail
cd /work
export ARCH=arm CROSS_COMPILE=arm-linux-gnueabihf-
JOBS=${JOBS:-8}
BB=/work/src/busybox-1.37.0
LINUX=/work/src/linux-7.2.7
LINUX_OUT=/work/out/linux-7.2.7
DROPBEAR=/work/src/dropbear-2026.94
if [ ! -f "$LINUX/drivers/clk/sunxi-ng/ccu-sun8i-v853.c" ]; then
    patch -d "$LINUX" -p1 < configs/linux-7.2.7-v853-stage1.patch
fi
if ! grep -q '"allwinner,sun8i-v853"' "$LINUX/arch/arm/mach-sunxi/sunxi.c"; then
    patch -d "$LINUX" -p1 < configs/0001-v853-machine.patch
fi
ROOTFS=/tmp/v851s-rootfs
mkdir -p out/busybox "$LINUX_OUT" "$ROOTFS"
if [ ! -f out/busybox/.config ]; then
    make -C "$BB" O=/work/out/busybox defconfig
    sed -i 's/# CONFIG_STATIC is not set/CONFIG_STATIC=y/' out/busybox/.config
    # Traffic-control interfaces in newer headers need not enter this initramfs.
    sed -i 's/CONFIG_TC=y/# CONFIG_TC is not set/' out/busybox/.config
    make -C "$BB" O=/work/out/busybox oldconfig </dev/null
fi
sed -i 's/CONFIG_SHA1_HWACCEL=y/# CONFIG_SHA1_HWACCEL is not set/;s/CONFIG_SHA256_HWACCEL=y/# CONFIG_SHA256_HWACCEL is not set/' out/busybox/.config
make -C "$BB" O=/work/out/busybox -j"$JOBS"
make -C "$BB" O=/work/out/busybox CONFIG_PREFIX="$ROOTFS" install
mkdir -p out/dropbear
if ! cmp -s configs/dropbear-localoptions.h out/dropbear/localoptions.h; then
    cp configs/dropbear-localoptions.h out/dropbear/localoptions.h
    if [ -f out/dropbear/Makefile ]; then make -C out/dropbear clean; fi
fi
if [ ! -f out/dropbear/Makefile ]; then
    (cd out/dropbear && "$DROPBEAR/configure" --host=arm-linux-gnueabihf \
        --enable-static --disable-zlib --disable-syslog --disable-lastlog \
        --disable-utmp --disable-wtmp)
fi
make -C out/dropbear -j"$JOBS" PROGRAMS=dropbear
if arm-linux-gnueabihf-readelf -l out/dropbear/dropbear | grep -q INTERP; then
    echo 'Dropbear has a dynamic program interpreter' >&2
    exit 1
fi
mkdir -p out/ssh "$ROOTFS/etc/dropbear" "$ROOTFS/root/.ssh"
if [ ! -f out/ssh/dropbear_ed25519_host_key ]; then
    (umask 077; dropbearkey -t ed25519 -f out/ssh/dropbear_ed25519_host_key)
fi
if [ ! -f out/ssh/client_ed25519 ]; then
    (umask 077; ssh-keygen -q -t ed25519 -N '' -f out/ssh/client_ed25519)
fi
install -m 755 out/dropbear/dropbear "$ROOTFS/usr/sbin/dropbear"
install -m 600 out/ssh/dropbear_ed25519_host_key "$ROOTFS/etc/dropbear/dropbear_ed25519_host_key"
install -m 600 out/ssh/client_ed25519.pub "$ROOTFS/root/.ssh/authorized_keys"
printf 'root:*:0:0:root:/root:/bin/sh\n' > "$ROOTFS/etc/passwd"
printf 'root:x:0:\n' > "$ROOTFS/etc/group"
printf '/bin/sh\n' > "$ROOTFS/etc/shells"
install -m 644 boot/udhcpd.conf "$ROOTFS/etc/udhcpd.conf"
cp boot/init "$ROOTFS/init"
chmod +x "$ROOTFS/init"
mkdir -p "$ROOTFS"/{dev,proc,sys,tmp,run}
if [ ! -e "$ROOTFS/dev/console" ]; then mknod "$ROOTFS/dev/console" c 5 1; fi
if [ ! -e "$ROOTFS/dev/null" ]; then mknod "$ROOTFS/dev/null" c 1 3; fi
(cd "$ROOTFS" && find . -print0 | LC_ALL=C sort -z | cpio --null -o --format=newc --owner=0:0) | gzip -n > out/initramfs.cpio.gz
cp configs/sun8i-v851s-dongle-stage1.dts "$LINUX/arch/arm/boot/dts/allwinner/"
if ! grep -q sun8i-v851s-dongle-stage1 "$LINUX/arch/arm/boot/dts/allwinner/Makefile"; then
    echo 'dtb-$(CONFIG_MACH_SUN8I) += sun8i-v851s-dongle-stage1.dtb' >> "$LINUX/arch/arm/boot/dts/allwinner/Makefile"
fi
make -C "$LINUX" O="$LINUX_OUT" KCONFIG_ALLCONFIG=/work/configs/kernel.config allnoconfig
for symbol in ARCH_SUNXI SUNXI_CCU SUN8I_V853_CCU SUN8I_V853_R_CCU \
    PINCTRL_SUN8I_V853 USB_MUSB_SUNXI PHY_SUN4I_USB \
    NET PACKET UNIX INET NETDEVICES COMPAT_32BIT_TIME CONFIGFS_FS USB_CONFIGFS \
    USB_CONFIGFS_ACM USB_CONFIGFS_NCM USB_F_ACM USB_F_NCM \
    U_SERIAL_CONSOLE \
    BLK_DEV_INITRD RD_GZIP DEVTMPFS BINFMT_ELF BINFMT_SCRIPT ARM_ARCH_TIMER \
    DEVMEM PSTORE PSTORE_RAM PSTORE_CONSOLE; do
    grep -qx "CONFIG_${symbol}=y" "$LINUX_OUT/.config" || { echo "Missing required CONFIG_${symbol}" >&2; exit 1; }
done
make -C "$LINUX" O="$LINUX_OUT" -j"$JOBS" zImage allwinner/sun8i-v851s-dongle-stage1.dtb
cp "$LINUX_OUT/arch/arm/boot/zImage" out/zImage
cp "$LINUX_OUT/arch/arm/boot/dts/allwinner/sun8i-v851s-dongle-stage1.dtb" out/board.dtb
fdtput -t x out/board.dtb /chosen linux,initrd-end "$(printf '%x' $((0x44000000 + $(stat -c%s out/initramfs.cpio.gz))))"
sha256sum out/zImage out/board.dtb out/initramfs.cpio.gz > out/SHA256SUMS
