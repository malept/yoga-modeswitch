USER_AUTOSTART = $(HOME)/.config/autostart
USER_BIN ?= $(HOME)/.local/bin

install:
	mkdir -p $(USER_AUTOSTART)
	cp autostart.desktop $(USER_AUTOSTART)/yoga-modeswitch.desktop
	mkdir -p $(USER_BIN)
	cp yoga-modeswitch.py $(USER_BIN)/

system-install:
	cp autostart.desktop /etc/xdg/autostart/yoga-modeswitch.desktop
	cp yoga-modeswitch.py /usr/local/bin/

.PHONY: install system-install
