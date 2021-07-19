all: install

SRCDIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))


# Check that we've got certain programs installed
define check_program_installed
ifeq ($$(shell which $(1)),)
$$(error "Must install $(1)!")
endif
endef

$(eval $(call check_program_installed,python3))
$(eval $(call check_program_installed,rsync))
$(eval $(call check_program_installed,envsubst))
$(eval $(call check_program_installed,systemctl))

# Remind the user that they need a `config/id_rsa` file
define check_file_exists
$(1):
	@echo "ERROR: You must provide a '$(1)' file!"
	@exit 1
install: $(1)
endef
$(eval $(call check_file_exists,config/id_rsa))
$(eval $(call check_file_exists,config/config.py))

# Install rules for static `ffmpeg` executable
FFMPEG_URL="https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-armhf-static.tar.xz"
$(SRCDIR)/dist/bin/ffmpeg:
	@mkdir -p $(SRCDIR)/dist/bin
	@curl -# -fL "$(FFMPEG_URL)" | tar -C $(SRCDIR)/dist/bin -Jx --strip-components=1 --wildcards "ffmpeg-*-armhf-static/ffmpeg"
install: $(SRCDIR)/dist/bin/ffmpeg

# Install rules for `systemd` services/timers
define install_systemd_files
# Install `.service`
$(HOME)/.config/systemd/user/$(1).service: $(1).service
	SRCDIR="$(SRCDIR)" PYTHON="$(shell which python3)" envsubst < "$$<" > "$$@"
install: $(HOME)/.config/systemd/user/$(1).service

# Install `.timer`
$(HOME)/.config/systemd/user/$(1).timer: $(1).timer
	cp "$$<" "$$@"
install: $(HOME)/.config/systemd/user/$(1).timer
endef

$(eval $(call install_systemd_files,panopticon_capture))
$(eval $(call install_systemd_files,panopticon_encode))


install:
	# Tell systemctl to start the `panopticon`.
	systemctl --user daemon-reload
	systemctl --user enable panopticon_capture.timer
	systemctl --user start panopticon_capture.timer
