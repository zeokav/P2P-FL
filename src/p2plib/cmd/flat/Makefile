UNAME := $(shell uname)

all: libp2p.so bench

libp2p.so:
	go build -buildmode=c-shared -o $@ flat.go

bench:
	go build -o $@ bench.go

clean:
	rm -f libp2p.* bench
