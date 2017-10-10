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

LIBRARY_FILES = bin/larpix.o bin/larpix.so

all: $(BINARIES) $(LIBRARY_FILES)

bin/larpix-control: src/main.c bin/larpix.o
	$(CC) -o $@ $^ $(CFLAGS)

bin/larpix.o: src/larpix.c include/larpix.h
	$(CC) -c -o $@ $< $(CFLAGS)

bin/larpix.so: src/larpix.c include/larpix.h
	$(CC) -shared -o $@ -fPIC $< $(CFLAGS)

TEST = bin/test
check: $(TEST)
	$<

TESTS = tests/UartTest.c tests/ConfigTest.c
$(TEST): tests/AllTests.c tests/CuTest.c $(TESTS) $(LIBRARY_FILES)
	$(CC) -o $@ $^ $(CFLAGS)
