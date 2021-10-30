package main

/*
   typedef void (*convert) ();

   static inline void call_c_func(convert ptr, char* data) {
   (ptr)(data);
   }

   static inline void call_c_func2(convert ptr, int num) {
               (ptr)(num);
   }
 */
import "C"

import (
	"bufio"
	"context"
	"errors"
	"fmt"
	"github.com/theued/p2plib"
	"github.com/theued/p2plib/kademlia"
	"io"
	"os"
	"strings"
	"time"
	"net"
	"unsafe"
	"go.uber.org/zap"
	"strconv"
	"sync"
       )

const (
	//server
	OP_RECV                      = 0x00
	OP_CLIENT_WAKE_UP            = 0x01
	OP_CLIENT_READY              = 0x02
	OP_CLIENT_UPDATE             = 0x03
	OP_CLIENT_EVAL               = 0x04
	//client
	OP_INIT                      = 0x05
	OP_REQUEST_UPDATE            = 0x06
	OP_STOP_AND_EVAL             = 0x07

	OP_BENCH_REQ                 = 0x08
	OP_BENCH_RESP                = 0x09
      )

type ops struct {
    on_recv C.convert
	//server
	on_wakeup C.convert
	on_clientready C.convert
	on_clientupdate C.convert
	on_clienteval C.convert
	//client
	on_init C.convert
	on_initfw C.convert
	on_requestupdate C.convert
	on_requestupdatefw C.convert
	on_stopandeval C.convert
}

var (
	node *p2plib.Node
	overlay *kademlia.Protocol
	events kademlia.Events
	callbacks ops
	max_peers=300
	//bench_cnt=0
	//repeat=0
	num_peers=0
	done_peers=0
	mutex_bench *sync.Mutex
	starttime time.Time
	dummydata []byte
    )

type chatMessage struct {
    opcode byte
	contents []byte
}

func (m chatMessage) Marshal() []byte {
    return append([]byte{m.opcode}, m.contents...)
}

func unmarshalChatMessage(buf []byte) (chatMessage, error) {
    return chatMessage{opcode: buf[0], contents: buf[1:]}, nil
}

// check panics if err is not nil.
func check(err error) {
    if err != nil {
	panic(err)
    }
}

// printedLength is the total prefix length of a public key associated to a chat users ID.
const printedLength = 8

func main() {
    args := os.Args[1:]
    port, err := strconv.Atoi(args[1])
    if err != nil {
        // Add code here to handle the error!
    }
    fmt.Printf("start main\n")

    init_p2p(string(args[0]), port)

    if len(args) == 3 {
        bootstrapping(string(args[2]))
    }

    // block here
    Input()
}

//export Init_p2p
func Init_p2p(host *C.char, port int) {
        init_p2p(C.GoString(host), port)
}

//export Bootstrapping
func Bootstrapping(serveraddr *C.char) {
        bootstrapping(C.GoString(serveraddr))
}

func init_p2p(host string, port int){
        var err error
	fmt.Printf("host : %s port : %d \n",host,port)

	mutex_bench = &sync.Mutex{}

	logger, _ := zap.NewProduction()
	// Create a new configured node.
	node, err = p2plib.NewNode(
		p2plib.WithNodeBindHost(net.ParseIP(host)),
		p2plib.WithNodeBindPort(uint16(port)),
		p2plib.WithNodeMaxRecvMessageSize(1<<24),
		p2plib.WithNodeMaxInboundConnections(300),
                p2plib.WithNodeMaxOutboundConnections(300),
		p2plib.WithNodeLogger(logger),
		)
	check(err)

	// Release resources associated to node at the end of the program.
	//defer node.Close()

	// Register the chatMessage Go type to the node with an associated unmarshal function.
	node.RegisterMessage(chatMessage{}, unmarshalChatMessage)

	// Register a message handler to the node.
	node.Handle(handle)

	// Instantiate Kademlia.
	events = kademlia.Events{
                    OnPeerAdmitted: func(id p2plib.ID) {
		    fmt.Printf("Learned about a new peer %s(%s).\n", id.Address, id.ID.String()[:printedLength])
		},
                   OnPeerEvicted: func(id p2plib.ID) {
		   fmt.Printf("Forgotten a peer %s(%s).\n", id.Address, id.ID.String()[:printedLength])
	       },
	}

        overlay = kademlia.New(kademlia.WithProtocolEvents(events),
	          kademlia.WithProtocolMaxNeighbors(max_peers),)

	// Bind Kademlia to the node.
	node.Bind(overlay.Protocol())

	fmt.Printf("start listen\n")
	// Have the node start listening for new peers.
	check(node.Listen())

	// Print out the nodes ID and a help message comprised of commands.
	help(node)
	/*
	   fmt.Printf("cmd : ")
	// Accept chat message inputs and handle chat commands in a separate goroutine.
	go input(func(line string) {
	chat(node, overlay, line)
	})

	// Wait until Ctrl+C or a termination call is done.
	c := make(chan os.Signal, 1)
	signal.Notify(c, os.Interrupt)
	<-c

	// Close stdin to kill the input goroutine.
	check(os.Stdin.Close())

	// Empty println.
	println()

	 */
	fmt.Printf("init done\n")
}

func bootstrapping(serveraddr string) {
    fmt.Printf("start bootstrap %s\n",serveraddr)
	// Ping nodes to initially bootstrap and discover peers from.
	bootstrap(serveraddr)
	/*
	   fmt.Printf("start discover\n")
	// Attempt to discover peers if we are bootstrapped to any nodes.
	discover(overlay)
	 */
}

//export Input
func Input() {
r := bufio.NewReader(os.Stdin)

       for {
	   buf, _, err := r.ReadLine()
	       if err != nil {
		   if errors.Is(err, io.EOF) {
		       return
		   }

		   check(err)
	       }

line := string(buf)
	  if len(line) == 0 {
	      continue
	  }

      fmt.Printf(line)
	  chat(line)
       }
}

// handle handles and prints out valid chat messages from peers.
func handle(ctx p2plib.HandlerContext) error {
    if ctx.IsRequest() {
	return nil
    }

    obj, err := ctx.DecodeMessage()
	if err != nil {
	    fmt.Printf("Decode fail recv msg from %s(%s)\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength])
		return nil
	}
    msg, ok := obj.(chatMessage)
	if !ok {
	    fmt.Printf("not ok fail recv msg from %s(%s)\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength])
		return nil
	}

    if len(msg.contents) == 0 {
	fmt.Printf("contents empty fail recv msg from %s(%s)\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength])
	    return nil
    }

    //fmt.Printf("recv msg from %s(%s) opcode : %v\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.opcode)
    ptr := unsafe.Pointer(&msg.contents[0])

    if msg.opcode == OP_RECV {
        C.call_c_func(callbacks.on_recv, (*C.char)(ptr) )
    }

    //server handler
    if msg.opcode == OP_CLIENT_WAKE_UP {
	C.call_c_func(callbacks.on_wakeup, (*C.char)(ptr) )
    }
    if msg.opcode == OP_CLIENT_READY {
	C.call_c_func(callbacks.on_clientready, (*C.char)(ptr) )
    }
    if msg.opcode == OP_CLIENT_UPDATE {
	C.call_c_func(callbacks.on_clientupdate, (*C.char)(ptr) )
    }
    if msg.opcode == OP_CLIENT_EVAL {
	C.call_c_func(callbacks.on_clienteval, (*C.char)(ptr) )
    }

    //client handler
    if msg.opcode == OP_INIT {
	C.call_c_func(callbacks.on_init, (*C.char)(ptr) )
    }
    if msg.opcode == OP_REQUEST_UPDATE {
	C.call_c_func(callbacks.on_requestupdate, (*C.char)(ptr) )
    }
    if msg.opcode == OP_STOP_AND_EVAL {
	C.call_c_func(callbacks.on_stopandeval, (*C.char)(ptr) )
    }

    if msg.opcode == OP_BENCH_REQ {
        sendMessage(ctx.ID() , msg.contents, OP_BENCH_RESP, kademlia.OP_ONE_TIME)
	msg.contents = nil
    }

    if msg.opcode == OP_BENCH_RESP {
	mutex_bench.Lock()
	//bench_cnt++
	done_peers++
	mutex_bench.Unlock()
        //fmt.Printf("bench_cnt:%d \n", bench_cnt)
        //if bench_cnt >= repeat {
	    //duration := time.Since(starttime)
            //fmt.Printf("DONE repeat:%d time:%s \n", bench_cnt,duration)
            if done_peers >= num_peers {
	        duration := time.Since(starttime)
                fmt.Printf("DONE %d peers time:%s \n", done_peers, duration)
	    }
        //}
	msg.contents = nil
    }

    return nil
}

// help prints out the users ID and commands available.
func help(node *p2plib.Node) {
    fmt.Printf("Your ID is %s(%s). Type '/discover' to attempt to discover new "+
	    "peers, or '/peers' to list out all peers you are connected to.\n",
	    node.ID().Address,
	    node.ID().ID.String()[:printedLength],
	    )
}

// bootstrap pings and dials an array of network addresses which we may interact with and  discover peers from.
//func bootstrap(node *p2plib.Node, addresses *C.char) {
func bootstrap(addr string) {
    fmt.Printf("run bootstrap on %s\n", addr)
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	_, err := node.Ping(ctx, addr, kademlia.OP_NEW_CONN) // NEW_CONN opcode requires server node register this node by replacing with existing one

	cancel()

	if err != nil {
	    fmt.Printf("Failed to ping bootstrap node (%s). Skipping... [error: %s]\n", addr, err)
	}
}

// discover uses Kademlia to discover new peers from nodes we already are aware of.
func discover(overlay *kademlia.Protocol) {
ids := overlay.Discover()

	 var str []string
	 for _, id := range ids {
	     str = append(str, fmt.Sprintf("%s(%s)", id.Address, id.ID.String()[:printedLength]))
	 }

     if len(ids) > 0 {
	 fmt.Printf("Discovered %d peer(s): [%v]\n", len(ids), strings.Join(str, ", "))
     } else {
	 fmt.Printf("Did not discover any peers.\n")
     }
}

// peers prints out all peers we are already aware of.
func peers(overlay *kademlia.Protocol) {
ids := overlay.Table().Peers()

	 var str []string
	 for _, id := range ids {
	     str = append(str, fmt.Sprintf("%s(%s)", id.Address, id.ID.String()[:printedLength]))
	 }

     fmt.Printf("You know %d peer(s): [%v]\n", len(ids), strings.Join(str, ", "))
}

func chat(line string) {
    switch line {
	case "/discover":
	    discover(overlay)
		return
	case "/peers":
		peers(overlay)
		return
	case "/bench":
		bench()
		return

	default:
    }

    if strings.HasPrefix(line, "/") {
	help(node)
	    return
    }
    /*
       for _, id := range overlay.Table().Peers() {
       ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
b := []byte(line)
err := node.SendMessage(ctx, id.Address, chatMessage{contents: b})
cancel()
if err != nil {
fmt.Printf("Failed to send message to %s(%s). Skipping... [error: %s]\n",
id.Address,
id.ID.String()[:printedLength],
err,
)
continue
}
}
     */

}

//export Write
func Write(src *C.char, size C.int, opcode byte) {
    for _, id := range overlay.Table().Peers() {
	ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
	    data := C.GoBytes(unsafe.Pointer(src), C.int(size))
	    err := node.SendMessage(ctx, id.Address, chatMessage{opcode: opcode, contents: data}, kademlia.OP_ONE_TIME)
	    /*
	    fmt.Printf("Send message to %s(%s) opcode: %v\n",
		    id.Address,
		    id.ID.String()[:printedLength],
		    opcode,
		    )
	    */
	    cancel()
	    if err != nil {
		fmt.Printf("Failed to send message to %s(%s). Skipping... [error: %s]\n",
			id.Address,
			id.ID.String()[:printedLength],
			err,
			)
		    continue
	    }
    }
}

//export Register_callback
func Register_callback(name *C.char, fn C.convert) {
    fmt.Printf("register callback : %s\n",C.GoString(name))
	if C.GoString(name) == "on_recv" {
	    fmt.Printf("on_recv registered\n")
		callbacks.on_recv = fn
	}
    //server handler
    if C.GoString(name) == "on_wakeup" {
	fmt.Printf("on_wakeup registered\n")
	    callbacks.on_wakeup = fn
    }
    if C.GoString(name) == "on_clientready" {
	fmt.Printf("on_clientready registered\n")
	    callbacks.on_clientready = fn
    }
    if C.GoString(name) == "on_clientupdate" {
	fmt.Printf("on_clientupdate registered\n")
	    callbacks.on_clientupdate = fn
    }
    if C.GoString(name) == "on_clienteval" {
	fmt.Printf("on_clienteval registered\n")
	    callbacks.on_clienteval = fn
    }
    //client handler
    if C.GoString(name) == "on_init" {
	fmt.Printf("on_init registered\n")
	    callbacks.on_init = fn
    }
    if C.GoString(name) == "on_request_update" {
	fmt.Printf("on_request_update registered\n")
	    callbacks.on_requestupdate = fn
    }
    if C.GoString(name) == "on_stop_and_eval" {
	fmt.Printf("on_stop_and_eval registered\n")
	    callbacks.on_stopandeval = fn
    }
}

func bench() {
    //datasize:=1073741824 //1GB
    //datasize:=268435456 //256MB
    //datasize:=67108864 //64MB
    //datasize:=16770000 //16MB
    //datasize:=4194304 //4MB
    //datasize:=1048576 //1MB
    //datasize:=262144 //256KB
    //datasize:=65536 //64KB
    //datasize:=16384 //16KB
    //datasize:=4096 //4KB
    datasize:=1024 //1KB
    //bench_cnt=0
    //repeat=1
    num_peers=200
    done_peers=0
    id := node.ID()
    dummydata = make([]byte, datasize)
    //fmt.Printf("message size:%d repeat:%d \n", len(dummydata), repeat)
    fmt.Printf("message size:%d num_peers:%d \n", len(dummydata), num_peers)
    starttime = time.Now() //It will return time.Time object with current timestamp
    //fmt.Printf("Start Time %s\n", starttime)
    //for i := 0; i < repeat; i++ {
        broadcast(id, dummydata, OP_BENCH_REQ)
    //}
    dummydata = nil
}

func sendMessage(addr p2plib.ID , data []byte, opcode byte, protocolOpcode byte ) {
        //ctx, cancel := context.WithTimeout(context.Background(), 3*time.Second)
        ctx, cancel := context.WithCancel(context.Background())
	err := node.SendMessage(ctx, addr.Address, chatMessage{opcode: opcode, contents: data}, protocolOpcode)
	/*
	fmt.Printf("Send message to %s(%s) opcode: %d\n",
	   addr.Address,
	   addr.ID.String()[:printedLength],
	   opcode,
	)
	*/
	if err != nil {
	    fmt.Printf("Failed to send message to %s. Skipping... [error: %s]\n",
		    addr.ID.String()[:printedLength],
		    err,
		    )
		cancel()
	}
}

func broadcast(sender p2plib.ID, data []byte , opcode byte){
       peers := overlay.Table().Peers()

       //var wg sync.WaitGroup

       for _, id := range peers {
	   if id.ID == sender.ID {
	       fmt.Printf("skip sender %v %v\n", id.ID.String()[:printedLength], sender.ID.String()[:printedLength])
	       continue
	   }

	   //wg.Add(1)

	   //go func() {
	   //defer wg.Done()

	   msgctx, cancel := context.WithCancel(context.Background())
	   err := node.SendMessage(msgctx, id.Address, chatMessage{opcode: opcode, contents: data}, kademlia.OP_ONE_TIME)
	   /*
	   fmt.Printf("Send message to %s(%s) opcode %d\n",
	       id.Address,
	       id.ID.String()[:printedLength],
	       opcode,
	   )
	   */
	   if err != nil {
	        fmt.Printf("Fail to send message to %s(%s)\n",
			   id.Address,
			   id.ID.String()[:printedLength],
		)
		cancel()
		continue
	   }

	   //}() //go func
       }
       //wg.Wait()
}

