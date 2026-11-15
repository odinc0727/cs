CC := cc
CFLAGS := -O2 -Wall -Wextra
PYTHON := uv run

ifeq ($(OS), Windows_NT)
    TARGET := math.dll
    SHARED_FLAGS := -shared
else
    UNAME_S := $(shell uname -s)
    ifeq ($(UNAME_S), Darwin)
        TARGET := libmath.dylib
        SHARED_FLAGS := -dynamiclib -fPIC
    else
        TARGET := libmath.so
        SHARED_FLAGS := -shared -fPIC
    endif
endif

.PHONY: all run clean

all: $(TARGET)

$(TARGET): lib.c
	$(CC) $(CFLAGS) $(SHARED_FLAGS) -o $@ $<

run: $(TARGET)
	$(PYTHON) main.py

clean:
	$(RM) libmath.so libmath.dylib math.dll
