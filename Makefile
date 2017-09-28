# From d2xx/examples/Rules.make
DEPENDENCIES := -lftd2xx -lpthread

UNAME := $(shell uname)
# Assume target is Mac OS if build host is Darwin; any other host
# targets Linux
ifeq ($(UNAME), Darwin)
    DEPENDENCIES += -lobjc -framework IOKit -framework CoreFoundation
else
    DEPENDENCIES += -lrt
endif

CFLAGS = -Wall -Wextra -I./include $(DEPENDENCIES) $(LINKER_OPTIONS)
# End snippet from d2xx/examples/Rules.make

BINARIES = bin/larpix-control

all: $(BINARIES)

bin/larpix-control: src/main.c bin/larpix.o
	$(CC) -o $@ $^ $(CFLAGS)

bin/larpix.o: src/larpix.c include/larpix.h
	$(CC) -c -o $@ $< $(CFLAGS)
