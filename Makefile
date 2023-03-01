all: image

SRCDIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))

# Let's goooo
IMG_NAME := panopticon
IMG_VERSION := v1


build:
	@mkdir -p $@


# Rules to clone/prepare `pi-gen` to generate the base image for us
pi-gen/.git/HEAD:
	git clone -b "sf/panopticon" https://github.com/staticfloat/pi-gen

pi-gen/config: etc/pi-gen.config pi-gen/.git/HEAD
	@IMG_NAME="$(IMG_NAME)" IMG_VERSION="$(IMG_VERSION)" envsubst <"$<" >"$@"

IMG_BUILD_PATH := pi-gen/deploy/${IMG_NAME}-${IMG_VERSION}-qemu.img
$(IMG_BUILD_PATH): pi-gen/config
	@cd pi-gen && sudo ./build.sh

# This is used for qemu-based booting
BOOT_DIR := pi-gen/work/$(IMG_NAME)/stage2/rootfs/boot/

build/$(IMG_NAME)-$(IMG_VERSION).img: $(IMG_BUILD_PATH) | build
	cp $< $@
	power2g() { echo "x=(l($$1/(1024^3)))/l(2); scale=0; 2^((x+1)/1)" | bc -l; }; \
	IMG_SIZE_BYTES=$$(stat -c '%s' $<); \
	qemu-img resize -f raw $@ $$(power2g $${IMG_SIZE_BYTES})G

debug-image: build/$(IMG_NAME)-$(IMG_VERSION).img
	cp -f $< build/debug.img
	-$(call qemu_run,build/debug.img,/bin/bash)
	rm -f build/debug.img

# The base image that will be customized in the future
image: build/$(IMG_NAME)-$(IMG_VERSION).img
clean-image:
	sudo rm -f $(IMG_BUILD_PATH)
cleanall: clean-image



# This gets called with the following parameters:
#  $(1) - A `.img` to boot
#  $(2) - An optional `init` executable within that `.img`
#  $(3) - An optional TFTP directory
define qemu_run
	qemu-system-aarch64 \
		-M raspi3b \
		-cpu cortex-a72 \
		-dtb $(BOOT_DIR)/bcm2710-rpi-3-b-plus.dtb \
		-kernel $(BOOT_DIR)/kernel8.img \
		-append "ro earlyprintk console=ttyAMA0,115200 root=/dev/mmcblk0p2 rootdelay=1 kernel.panic=-1 $(if $(2),init=$(2),)" \
		-drive file=$(1),if=sd,format=raw \
		-netdev user,id=net0,$(if $(3),tftp=$(3),) \
		-device usb-net,netdev=net0 \
		-serial mon:stdio \
		-no-reboot \
		-nographic
endef


# This gets called with a config name
define bootstrap_builder
build/bootstrap-staging-$(1) build/bootstrap-tftp-$(1):
	@mkdir -p $$@

build/bootstrap-staging-$(1)/bootstrap.sh: bootstrap.sh | build/bootstrap-staging-$(1)
	@IMG_NAME="$(IMG_NAME)" \
	STATIC_IP_ADDR="$$(shell python3 ./src/config_print.py ./configs/$(1)/config.py static_ip 2>/dev/null || true)" \
	RSYNC_DEST_ADDR="$$(shell python3 ./src/config_print.py ./configs/$(1)/config.py rsync_dest)" \
	envsubst '$$$${IMG_NAME} $$$${STATIC_IP_ADDR} $$$${RSYNC_DEST_ADDR}' <bootstrap.sh >"$$@"
	@chmod +x "$$@"

build/bootstrap-staging-$(1)/src build/bootstrap-staging-$(1)/share build/bootstrap-staging-$(1)/etc: | build/bootstrap-staging-$(1)
	@rm -f $$@
	@ln -s ../../$$(notdir $$@) $$@

build/bootstrap-staging-$(1)/config: | build/bootstrap-staging-$(1)
	@rm -f $$@
	@ln -s ../../configs/$(1) $$@

build/bootstrap-tftp-$(1)/bootstrap.tar.gz: build/bootstrap-staging-$(1)/bootstrap.sh \
                                            build/bootstrap-staging-$(1)/src \
											$(wildcard src/*) \
											build/bootstrap-staging-$(1)/share \
											$(wildcard share/*) \
											build/bootstrap-staging-$(1)/etc \
											$(wildcard etc/*) \
											build/bootstrap-staging-$(1)/config \
											$(wildcard configs/$(1)/*) \
											build/bootstrap-tftp-$(1)
	@echo "Building bootstrap staging tarball $$(notdir $$@)..."
	@tar -chzf $$@ -C build/bootstrap-staging-$(1) .

build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img: build/bootstrap-tftp-$(1)/bootstrap.tar.gz build/$(IMG_NAME)-$(IMG_VERSION).img
	cp build/$(IMG_NAME)-$(IMG_VERSION).img $$@
	$$(call qemu_run,$$@,/usr/lib/qemu_customize,build/bootstrap-tftp-$(1))

customize-$(1): build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img

debug-$(1): build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img
	$$(call qemu_run,build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img,/bin/bash)

run-$(1): build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img
	$$(call qemu_run,build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img)

clean-image-$(1):
	rm -f build/$(IMG_NAME)-$(IMG_VERSION)-$(1).img
cleanall: clean-image-$(1)
clean: clean-image-$(1)
endef

$(eval $(call bootstrap_builder,eeville))

cleanall:
	rm -rf build
	sudo bash -c "source pi-gen/scripts/common && unmount pi-gen/work"
	sudo rm -rf pi-gen/work
	sudo rm -rf pi-gen/deploy
