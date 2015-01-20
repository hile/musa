
VERSION= $(shell awk -F\' '/^VERSION/ {print $$2}' setup.py)

SYSTEM= $(shell uname -s)
ifeq ($(SYSTEM),Darwin)
INSTALL_FLAGS='--no-user-cfg'
else
INSTALL_FLAGS=
endif

all: build

clean:
	@rm -rf build
	@rm -rf dist
	@find . -name '*.pyc' -o -name '*.egg-info'|xargs rm -rf

build:
	python setup.py build

ifdef PREFIX
install: build
	python setup.py $(INSTALL_FLAGS) install --prefix=${PREFIX}
else
install: build
	python setup.py install
endif

register:
	python setup.py register sdist upload

