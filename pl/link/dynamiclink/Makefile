CC := cc
CFLAGS := -O2 -Wall -Wextra

ifeq ($(OS), Windows_NT)
    LIB := math.dll
    APP := main.exe
    SHARED_FLAGS := -shared
    LDLIBS :=
else
    UNAME_S := $(shell uname -s)
    APP := main
    ifeq ($(UNAME_S), Darwin)
        LIB := libmath.dylib
        SHARED_FLAGS := -dynamiclib -fPIC
        LDLIBS :=
    else
        LIB := libmath.so
        SHARED_FLAGS := -shared -fPIC
        LDLIBS := -ldl
    endif
endif

.PHONY: all run clean

all: $(LIB) $(APP)

$(LIB): lib.c
	$(CC) $(CFLAGS) $(SHARED_FLAGS) -o $@ $<

$(APP): main.c
	$(CC) $(CFLAGS) -o $@ $< $(LDLIBS)

run: all
	./$(APP)

clean:
	$(RM) $(LIB) $(APP)
