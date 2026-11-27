CC ?= gcc
CFLAGS ?= -std=c11 -O2 -Wall -Wextra -Wpedantic
CPPFLAGS ?= -D_POSIX_C_SOURCE=200809L -Iinclude
LDFLAGS ?=
LDLIBS ?=

BUILDDIR := build
TARGET := $(BUILDDIR)/simulator
SRCS := src/common.c src/simulator.c src/fifo.c src/lru.c src/clock.c
HDRS := include/page_replacement.h

.PHONY: all build test clean help

all: $(TARGET)

$(TARGET): $(SRCS) $(HDRS)
	mkdir -p $(BUILDDIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) $(SRCS) -o $@ $(LDFLAGS) $(LDLIBS)

build: $(TARGET)

test: $(TARGET)
	python3 tests/run_tests.py --simulator $(TARGET)

help:
	@echo "make          build $(TARGET) with warnings enabled"
	@echo "make test     build, then run known-answer correctness tests"
	@echo "make clean    remove build artifacts"

clean:
	rm -rf $(BUILDDIR)
