all: install

SRCDIR := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))


# Check that we've got certain programs installed
define check_program_installed
ifeq ($$(shell which $(1)),)
$$(error "Must install $(1)!")
endif
endef

$(call check_program_installed,ffmpeg)
$(call check_program_installed,python)
$(call check_program_installed,rsync)
$(call check_program_installed,envsubst)
$(call check_program_installed,systemctl)

# Remind the user that they need a `config/id_rsa` file
config/id_rsa:
	echo "ERROR: You must provide an `id_rsa` file in `config!" >&2
	exit 1
install: config/id_rsa


# Install rules for `systemd` service
$(HOME)/.config/systemd/user/panopticon_capture.service: panopticon_capture.service
	SRCDIR="$(SRCDIR)" PYTHON="$(shell which python)" envsubst < "$<" > "$@"
install: $(HOME)/.config/systemd/user/panopticon_capture.service

# Install rules for `systemd` timer
$(HOME)/.config/systemd/user/panopticon_capture.timer: panopticon_capture.timer
	cp "$<" "$@"
install: $(HOME)/.config/systemd/user/panopticon_capture.timer


install:
	# Tell systemctl to start the `panopticon`.
	sudo systemctl daemon-reload
	sudo systemctl --user enable panopticon.timer
	sudo systemctl --user start panopticon.timer
