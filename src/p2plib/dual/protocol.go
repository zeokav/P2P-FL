package dual

import (
	"context"
	"errors"
	"fmt"
	"github.com/theued/p2plib"
	"go.uber.org/zap"
	"time"
	"strings"
	"sync"
	"github.com/VictoriaMetrics/fastcache"
	"bytes"
	 "encoding/json"
)

//protocol opcode
const (
        OP_BROADCAST                 = 0x01
        OP_GROUP_MULTICAST           = 0x02
	OP_REQUEST_GROUP             = 0x03
	OP_REQUEST_GROUP_SUB         = 0x04
        OP_REQUEST_JOIN              = 0x05
        OP_JOIN_GROUP                = 0x06

        OP_FED_COMP                  = 0x07
        OP_REPORT                    = 0x08

	OP_ONE_TIME                  = 0x09
        OP_NEW_CONN                  = 0x10
        OP_DISCOVER                  = 0x11

	// hybrid fed comp
	OP_FED_COMP_PUSH             = 0x12
	OP_FED_COMP_PULL_REQ         = 0x13
	OP_FED_COMP_PULL             = 0x14
	OP_FED_COMP_PULL_RESP        = 0x15
	OP_FED_COMP_PULL_RESP_DENY   = 0x16
)

//Identification state
const (
        ID_NOBODY                   = 0x00
        ID_INITIATOR                = 0x01
        ID_SUBLEADER                = 0x02
        ID_WORKER                   = 0x03
)

// BucketSize returns the capacity, or the total number of peer ID entries a single routing table bucket may hold.
const BucketSize int = 16

// printedLength is the total prefix length of a public key associated to a chat users ID.
const printedLength = 8

// ErrBucketFull is returned when a routing table bucket is at max capacity.
var ErrBucketFull = errors.New("bucket is full")

// Protocol implements routing/discovery portion of the Kademlia protocol with improvements suggested by the
// S/Kademlia paper. It is expected that Protocol is bound to a p2plib.Node via (*p2plib.Node).Bind before the node
// starts listening for incoming peers.
type Protocol struct {
	node   *p2plib.Node

	logger *zap.Logger

	table_bc  *Table
	table_gr  *Table

	maxNeighborsBC int
	maxNeighborsGR int
	leader string
	id_state byte

	events Events

	pingTimeout time.Duration

	mutex *sync.Mutex

	seen_push *fastcache.Cache
	seen_pull *fastcache.Cache
	mutex_push *sync.Mutex
	mutex_pull *sync.Mutex

        gossipmsg DownloadMessage
	//currentUUID []byte
	currentUUID string
	inUse bool
	mutex_msg *sync.Mutex
}

// New returns a new instance of the Kademlia protocol.
func New(opts ...ProtocolOption) *Protocol {
	p := &Protocol{
		pingTimeout: 3 * time.Second,
	        mutex: new(sync.Mutex),
	        maxNeighborsBC: 128,
	        maxNeighborsGR: 16,
		seen_push: fastcache.New(64 << 20),
		seen_pull: fastcache.New(64 << 20),
		mutex_push: new(sync.Mutex),
		mutex_pull: new(sync.Mutex),
		mutex_msg: new(sync.Mutex),
	}


	for _, opt := range opts {
		opt(p)
	}

	return p
}

func hash(id p2plib.ID, data []byte) []byte {
    return append(id.ID[:], data...)
}

//func(p *Protocol) markSeenPush(target p2plib.ID, uuid []byte) {
func(p *Protocol) markSeenPush(target p2plib.ID, euuid []byte) {
    // unmarshal
    var uuid string
    err := json.Unmarshal(euuid, &uuid)
    if err != nil {
       fmt.Printf("Error on decode process: %v\n", err)
    }
    p.mutex_push.Lock()
    p.seen_push.Set(hash(target, []byte(uuid)), nil)
    p.mutex_push.Unlock()
}


//func(p *Protocol) markSeenPull(target p2plib.ID, uuid []byte) {
func(p *Protocol) markSeenPull(target p2plib.ID, euuid []byte) {
    // unmarshal
    var uuid string
    err := json.Unmarshal(euuid, &uuid)
    if err != nil {
       fmt.Printf("Error on decode process: %v\n", err)
    }
    p.mutex_pull.Lock()
    p.seen_pull.Set(hash(target, []byte(uuid)), nil)
    p.mutex_pull.Unlock()
}

//func(p *Protocol) hasSeenPush(target p2plib.ID, uuid []byte) bool{
func(p *Protocol) hasSeenPush(target p2plib.ID, euuid []byte) bool{
    // unmarshal
    var uuid string
    err := json.Unmarshal(euuid, &uuid)
    if err != nil {
       fmt.Printf("Error on decode process: %v\n", err)
    }
    p.mutex_push.Lock()
    self := hash(target, []byte(uuid))
    if p.seen_push.Has(self) {
        p.mutex_push.Unlock()
        return true
    }
    p.mutex_push.Unlock()
    return false
}


//func(p *Protocol) hasSeenPull(target p2plib.ID, uuid []byte) bool{
func(p *Protocol) hasSeenPull(target p2plib.ID, euuid []byte) bool{
    // unmarshal
    var uuid string
    err := json.Unmarshal(euuid, &uuid)
    if err != nil {
       fmt.Printf("Error on decode process: %v\n", err)
    }
    p.mutex_pull.Lock()
    self := hash(target, []byte(uuid))
    if p.seen_pull.Has(self) {
        p.mutex_pull.Unlock()
        return true
    }
    p.mutex_pull.Unlock()
    return false
}

func(p *Protocol) SetUse() {
    p.mutex_msg.Lock()
    p.inUse = true
    p.mutex_msg.Unlock()
}

func(p *Protocol) DoneUse() {
    p.mutex_msg.Lock()
    p.inUse = false
    p.mutex_msg.Unlock()
}

func(p *Protocol) SetItem(msg DownloadMessage){
    p.gossipmsg = msg
}

func(p *Protocol) GetItem() DownloadMessage {
    return p.gossipmsg
}

//func(p *Protocol) HasUUID(uuid []byte) bool{
func(p *Protocol) HasUUID(euuid []byte) bool{
    // unmarshal
    var uuid string
    err := json.Unmarshal(euuid, &uuid)
    if err != nil {
         fmt.Printf("Error on decode process: %v\n", err)
    }
    // Comparing slice
    res := bytes.Compare([]byte(uuid), []byte(p.currentUUID))
      //res := bytes.Compare(uuid, p.currentUUID)
      if res == 0 {
          //fmt.Println("I have the item")
          return true
      } else {
          //fmt.Println("I don't have the item")
          return false
      }
}

//func(p *Protocol) SetUUID(uuid []byte){
func(p *Protocol) SetUUID(euuid []byte){
      // unmarshal
      var uuid string
      err := json.Unmarshal(euuid, &uuid)
      if err != nil {
         fmt.Printf("Error on decode process: %v\n", err)
      }
      p.currentUUID = uuid
}

// Find executes the FIND_NODE S/Kademlia RPC call to find the closest peers to some given target public key. It
// returns the IDs of the closest peers it finds.
func (p *Protocol) Find(target p2plib.PublicKey, opts ...IteratorOption) []p2plib.ID {
	return NewIterator(p.node, p.table_bc, opts...).Find(target)
}

// Discover attempts to discover new peers to your node through peers your node  already knows about by calling
// the FIND_NODE S/Kademlia RPC call with your nodes ID.
func (p *Protocol) DiscoverLocal(opts ...IteratorOption) []p2plib.ID {
	return p.Find(p.node.ID().ID, opts...)
}

// Discover attempts to discover new peers to your node through peers your node  already knows about by calling
// the FIND_NODE S/Kademlia RPC call with your nodes ID.
func (p *Protocol) DiscoverRandom(opts ...IteratorOption) []p2plib.ID {
        pub, _, _ := p2plib.GenerateKeys(nil)
	return p.Find(pub, opts...)
}

// Ping sends a ping request to addr, and returns no error if a p!!!ong is received back before ctx has expired/was
// cancelled. It also throws an error if the connection to addr intermittently drops, or if handshaking with addr
// should there be no live connection to addr yet fails.
func (p *Protocol) Ping(ctx context.Context, addr string) error {
        //fmt.Printf("protocol ping \n")
	msg, err := p.node.RequestMessage(ctx, addr, Ping{})
	if err != nil {
		return fmt.Errorf("failed to ping: %w", err)
	}

	if _, ok := msg.(Pong); !ok {
		return errors.New("did not get a pong back")
	}
        //fmt.Printf("receive protocol ping \n")

	return nil
}

func (p *Protocol) Lock() {
    p.mutex.Lock()
}

func (p *Protocol) Unlock() {
    p.mutex.Unlock()
}

// MaxNeighbors returns cap of routing table
func (p *Protocol) MaxNeighborsGR() int {
	return p.maxNeighborsGR
}

// MaxNeighbors returns cap of routing table
func (p *Protocol) MaxNeighborsBC() int {
	return p.maxNeighborsBC
}

// GetLeader returns the address of leader node
func (p *Protocol) GetLeader() string {
	return p.leader
}

// SetLeader sets the address of leader node
func (p *Protocol) SetLeader(addr string) {
	p.leader = addr
}

// GetID returns the identification of myself
func (p *Protocol) GetID() byte {
	return p.id_state
}

// SetID sets the identification of myself
func (p *Protocol) SetID(id byte) {
	p.id_state = id
}

// Table returns this Kademlia overlay's routing table from your nodes perspective.
func (p *Protocol) Table_bc() *Table {
	return p.table_bc
}

func (p *Protocol) Table_gr() *Table {
	return p.table_gr
}

func (p *Protocol) RemoveConn(id p2plib.ID) {
        if  p.table_bc.Recorded(id.ID) {
        /*
            client, exists := p.node.OutboundGet(id.Address)
            if exists {
                client.Close()
                client.WaitUntilClosed()
            }
            client, exists = p.node.InboundGet(id.Address)
            if exists {
                client.Close()
                client.WaitUntilClosed()
            }
        */
            if entryid, deleted := p.table_bc.Delete(id.ID); deleted {
		/*
                fmt.Printf("Peer %s(%s) is deleted from routing table\n",
                       entryid.Address,
	               entryid.ID.String()[:printedLength],
	        )
		*/
	        if p.events.OnPeerEvicted != nil {
	            //fmt.Printf("RemoveConn() bread1\n")
	            p.events.OnPeerEvicted(entryid)
                }
                return
            }
            /*
            fmt.Printf("Peer %s(%s) is not eleted\n",
                   id.Address,
                   id.ID.String()[:printedLength],
                  )
            */
        }
}

func (p *Protocol) ReplaceConn(id p2plib.ID) {
        if  p.table_bc.Recorded(id.ID) == false {
            //fmt.Printf("%s(%s) is not registered yet. Register first.\n",id.Address, id.ID.String()[:printedLength])
            inserted, err := p.table_bc.Update(id)
            if err == nil {
                if inserted {
                    p.logger.Debug("Peer was inserted into routing table.",
                                   zap.String("peer_id", id.String()),
                                   zap.String("peer_addr", id.Address),
                    )
                }
		if inserted {
			if p.events.OnPeerAdmitted_bc != nil {
				p.events.OnPeerAdmitted_bc(id)
			}
		} else {
			if p.events.OnPeerActivity != nil {
				p.events.OnPeerActivity(id)
			}
		}
            }
            /*
            //debug log
            for _, en := range p.table_bc.Entries() {
                fmt.Println(en)
            }
            */
        }

        entries := p.table_bc.Peers()
        for {
            entry := entries[len(entries)-1]
            entries = entries[:len(entries)-1]
            if id.ID == entry.ID {
                continue
            }
            p.RemoveConn(entry)
            break
        }
}

// Ack attempts to insert a peer ID into your nodes routing table. If the routing table bucket in which your peer ID
// was expected to be inserted on is full, the peer ID at the tail of the bucket is pinged. If the ping fails, the
// peer ID at the tail of the bucket is evicted and your peer ID is inserted to the head of the bucket.
func (p *Protocol) Ack_bc(id p2plib.ID, opcode ...byte) {

	if p.events.OnPeerContacted != nil {
		p.events.OnPeerContacted(id)
	}

        if p.table_bc.NumEntries() > p.maxNeighborsBC {
            //fmt.Errorf("Table BC is full \n")
	    /*
            for _, en := range p.table.Entries() {
               fmt.Println(en)
            }
            */

            if len(opcode) != 0 && (opcode[0] == byte(OP_NEW_CONN) || opcode[0] == byte(OP_DISCOVER)) {
                //fmt.Printf("replace with NEW_CONN %s %s\n",id.Address, id.ID.String()[:printedLength])
                p.ReplaceConn(id) // register current conn req and delete one of the existing one
            }
            // otherwise, just ignore conn req because table already reaches to maxNeighbors
	    return
	}

	for {
		inserted, err := p.table_bc.Update(id)
		if err == nil {
			if inserted {
				p.logger.Debug("Peer was inserted into routing table_bc.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
				)
			}

			if inserted {
				if p.events.OnPeerAdmitted_bc != nil {
					p.events.OnPeerAdmitted_bc(id)
				}
			} else {
				if p.events.OnPeerActivity != nil {
					p.events.OnPeerActivity(id)
				}
			}
			return
		}

		last := p.table_bc.Last(id.ID)

		ctx, cancel := context.WithTimeout(context.Background(), p.pingTimeout)
		pong, err := p.node.RequestMessage(ctx, last.Address, Ping{})
		cancel()

		if err != nil {
			if id, deleted := p.table_bc.Delete(last.ID); deleted {
				p.logger.Debug("Peer was evicted from routing table by failing to be pinged.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
					zap.Error(err),
				)

				if p.events.OnPeerEvicted != nil {
					p.events.OnPeerEvicted(id)
				}
			}
			continue
		}

		if _, ok := pong.(Pong); !ok {
			if id, deleted := p.table_bc.Delete(last.ID); deleted {
				p.logger.Debug("Peer was evicted from routing table_bc by failing to be pinged.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
					zap.Error(err),
				)

				if p.events.OnPeerEvicted != nil {
					p.events.OnPeerEvicted(id)
				}
			}
			continue
		}

		p.logger.Debug("Peer failed to be inserted into routing table_bc as it's intended bucket is full.",
			zap.String("peer_id", id.String()),
			zap.String("peer_addr", id.Address),
		)

		if p.events.OnPeerEvicted != nil {
			p.events.OnPeerEvicted(id)
		}

		return
	}
}


// Ack attempts to insert a peer ID into your nodes routing table. If the routing table bucket in which your peer ID
// was expected to be inserted on is full, the peer ID at the tail of the bucket is pinged. If the ping fails, the
// peer ID at the tail of the bucket is evicted and your peer ID is inserted to the head of the bucket.
func (p *Protocol) Ack_gr(id p2plib.ID) {

        if p.table_gr.NumEntries() > p.maxNeighborsGR {
            //fmt.Errorf("Table GR is full \n")
	    return
	}

	for {
		inserted, err := p.table_gr.Update(id)
		if err == nil {
			if inserted {
				p.logger.Debug("Peer was inserted into routing table_gr.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
				)
			}

			if inserted {
				if p.events.OnPeerAdmitted_gr != nil {
					p.events.OnPeerAdmitted_gr(id)
				}
			} else {
				if p.events.OnPeerActivity != nil {
					p.events.OnPeerActivity(id)
				}
			}

			return
		}

		last := p.table_gr.Last(id.ID)

		ctx, cancel := context.WithTimeout(context.Background(), p.pingTimeout)
		pong, err := p.node.RequestMessage(ctx, last.Address, Ping{})
		cancel()

		if err != nil {
			if id, deleted := p.table_gr.Delete(last.ID); deleted {
				p.logger.Debug("Peer was evicted from routing table_gr by failing to be pinged.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
					zap.Error(err),
				)

				if p.events.OnPeerEvicted != nil {
					p.events.OnPeerEvicted(id)
				}
			}
			continue
		}

		if _, ok := pong.(Pong); !ok {
			if id, deleted := p.table_gr.Delete(last.ID); deleted {
				p.logger.Debug("Peer was evicted from routing table_gr by failing to be pinged.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
					zap.Error(err),
				)

				if p.events.OnPeerEvicted != nil {
					p.events.OnPeerEvicted(id)
				}
			}
			continue
		}

		p.logger.Debug("Peer failed to be inserted into routing table_gr as it's intended bucket is full.",
			zap.String("peer_id", id.String()),
			zap.String("peer_addr", id.Address),
		)

		if p.events.OnPeerEvicted != nil {
			p.events.OnPeerEvicted(id)
		}

		return
	}
}

// Protocol returns a p2plib.Protocol that may registered to a node via (*p2plib.Node).Bind.
func (p *Protocol) Protocol() p2plib.Protocol {
	return p2plib.Protocol{
		Bind:            p.Bind,
		OnPeerConnected: p.OnPeerConnected,
		OnPingFailed:    p.OnPingFailed,
		OnMessageSent:   p.OnMessageSent,
		OnMessageRecv:   p.OnMessageRecv,
		OnExistingConnection:   p.OnExistingConnection,
	}
}

// Bind registers messages Ping, Pong, FindNodeRequest, FindNodeResponse, and handles them by registering the
// (*Protocol).Handle Handler.
func (p *Protocol) Bind(node *p2plib.Node) error {
	p.node = node
	p.table_bc = NewTable(p.node.ID())
	p.table_gr = NewTable(p.node.ID())

	if p.logger == nil {
		p.logger = p.node.Logger()
	}

	node.RegisterMessage(Ping{}, UnmarshalPing)
	node.RegisterMessage(Pong{}, UnmarshalPong)
	node.RegisterMessage(FindNodeRequest{}, UnmarshalFindNodeRequest)
	node.RegisterMessage(FindNodeResponse{}, UnmarshalFindNodeResponse)
	node.RegisterMessage(P2pMessage{}, unmarshalP2pMessage)
	node.RegisterMessage(GossipMessage{}, UnmarshalGossipMessage)
	node.RegisterMessage(Request{}, UnmarshalRequest)
	node.RegisterMessage(DownloadMessage{}, UnmarshalDownloadMessage)
	node.RegisterMessage(Deny{}, UnmarshalDeny)

	node.Handle(p.Handle)


	return nil
}

func (p *Protocol) OnExistingConnection(isInbound bool, client *p2plib.Client, opcode ...byte) {
        if len(opcode) == 0 {
            //fmt.Printf("OnExistingConnection no opcode \n")
	    return
	}
	if opcode[0] == byte(OP_GROUP_MULTICAST) && !isInbound {
            //fmt.Printf("OnExistingConnection GROUP MULTICAST\n")
            p.Ack_gr(client.ID())
	}
}

// OnPeerConnected attempts to acknowledge the new peers existence by placing its entry into your nodes' routing table
// via (*Protocol).Ack.
func (p *Protocol) OnPeerConnected(isInbound bool, client *p2plib.Client, opcode ...byte) {
	if len(opcode) != 0 && opcode[0] == byte(OP_ONE_TIME) {
            fmt.Printf("One time message without registering in routing table\n")
	    return
        }
/*
	if len(opcode) != 0 && opcode[0] == byte(OP_DISCOVER) && !isInbound {
            fmt.Printf("we don't register incoming querying nodes\n")
	    return
        }
*/
	if len(opcode) != 0 && opcode[0] == byte(OP_GROUP_MULTICAST) && !isInbound {
            fmt.Printf(" OnPeerConnected GROUP MULTICAST opcode\n")
	    p.Ack_gr(client.ID())
	    return
	}

	p.Ack_bc(client.ID(), opcode...)
	return
}

// OnPingFailed evicts peers that your node has failed to dial.
func (p *Protocol) OnPingFailed(addr string, err error) {
	if id, deleted := p.table_bc.DeleteByAddress(addr); deleted {
		p.logger.Debug("Peer was evicted from routing table_bc by failing to be dialed.", zap.Error(err))

		if p.events.OnPeerEvicted != nil {
			p.events.OnPeerEvicted(id)
		}
	}
}

// OnMessageSent implements p2plib.Protocol and attempts to push the position in which the clients ID resides in
// your nodes' routing table's to the head of the bucket it reside within.
func (p *Protocol) OnMessageSent(client *p2plib.Client, opcode ...byte) {
    /*
    if len(opcode) != 0 && opcode[0] == byte(OP_ONE_TIME) {
        //fmt.Printf("One time message without registering in routing table\n")
    }else{
	p.Ack_bc(client.ID(), opcode...)
    }
    */
}

// OnMessageRecv implements p2plib.Protocol and attempts to push the position in which the clients ID resides in
// your nodes' routing table's to the head of the bucket it reside within.
func (p *Protocol) OnMessageRecv(client *p2plib.Client, opcode ...byte) {
    /*
    if len(opcode) != 0 && opcode[0] == byte(OP_ONE_TIME) {
        //fmt.Printf("One time message without registering in routing table\n")
    }else{
	p.Ack_bc(client.ID(), opcode...)
    }
    */
}

// Handle implements p2plib.Protocol and handles Ping and FindNodeRequest messages.
func (p *Protocol) Handle(ctx p2plib.HandlerContext) error {
	msg, err := ctx.DecodeMessage()
	if err != nil {
		return nil
	}

	switch msg := msg.(type) {
	case Ping:
		if !ctx.IsRequest() {
			return errors.New("got a ping that was not sent as a request")
		}
		return ctx.SendMessage(Pong{})
	case FindNodeRequest:
		if !ctx.IsRequest() {
			return errors.New("got a find node request that was not sent as a request")
		}
		return ctx.SendMessage(FindNodeResponse{Results: p.table_bc.FindClosest(msg.Target, BucketSize)})
	case P2pMessage:
		//fmt.Printf("recv p2p msg from %s(%s) opcode : %v\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.Opcode)

	        if msg.Opcode == OP_REQUEST_GROUP {
		    // register sender as leader
		    p.SetLeader(ctx.ID().Address)
		    //fmt.Printf("leader : %s\n",p.GetLeader())

		    p.SetID(ID_INITIATOR)
		    //fmt.Printf("I am : %d (1:initiator, 2:subleader, 3:worker)\n",p.GetID())
                    if p.events.OnRequestGroup != nil {
		        //p.events.OnRequestGroup(msg.Contents)
		        p.events.OnRequestGroup(msg)
	            }
	        }

	        if msg.Opcode == OP_REQUEST_GROUP_SUB {
		    // register sender as leader
		    p.SetLeader(ctx.ID().Address)
		    //fmt.Printf("leader : %s\n",p.GetLeader())

		    p.SetID(ID_SUBLEADER)
		    //fmt.Printf("I am : %d (1:initiator, 2:subleader, 3:worker)\n",p.GetID())
                    if p.events.OnRequestGroupSub != nil {
		        //p.events.OnRequestGroupSub(msg.Contents)
		        p.events.OnRequestGroupSub(msg)
	            }
	        }

                if msg.Opcode == OP_REQUEST_JOIN{
		    // register sender as leader
		    p.SetLeader(ctx.ID().Address)
		    //fmt.Printf("leader : %s\n",p.GetLeader())

		    p.SetID(ID_WORKER)
		    //fmt.Printf("I am : %d (1:initiator, 2:subleader, 3:worker)\n",p.GetID())
                    if p.events.OnRequestJoin != nil {
		        //p.events.OnRequestJoin(msg.Contents)
		        p.events.OnRequestJoin(msg)
	            }
                }

                if msg.Opcode == OP_JOIN_GROUP{
                    if p.events.OnJoinGroup != nil {
		        //p.events.OnJoinGroup(msg.Contents)
		        p.events.OnJoinGroup(msg)
	            }
                }

                if msg.Opcode == OP_FED_COMP{
                    if p.events.OnFedComputation != nil {
		        //p.events.OnFedComputation(msg.Contents)
		        p.events.OnFedComputation(msg)
	            }
                }

                if msg.Opcode == OP_REPORT{
                    if p.events.OnReport != nil {
		        //p.events.OnReport(msg.Contents)
		        p.events.OnReport(msg)
	            }
                }
		break
        case GossipMessage:
               if msg.Opcode == OP_FED_COMP_PUSH{
                   //fmt.Printf("recv OP_FED_COMP_PUSH from %s(%s) opcode : %v\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.Opcode)

                    p.markSeenPush(ctx.ID(), msg.UUID) //mark this message from sender
                    if p.hasSeenPush(p.node.ID(), msg.UUID) { // check if we have received
                       //fmt.Printf("skip OP_FED_COMP_PUSH from %s(%s) opcode : %v\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.Opcode)
                       return nil
                    }
                    p.markSeenPush(p.node.ID(), msg.UUID) //otherwise, mark it

                    // save item for pull request
                    p.SetItem(DownloadMessage{UUID: msg.UUID, Contents: msg.Contents})
                    p.SetUUID(msg.UUID)

                    if p.events.OnFedComputationPush != nil {
	                 p.events.OnFedComputationPush(msg,ctx)
	            }
	       }

	       if msg.Opcode == OP_FED_COMP_PULL_REQ{
                   //fmt.Printf("recv OP_FED_COMP_PULL_REQ from %s(%s) opcode : %v\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.Opcode)
                    p.markSeenPull(ctx.ID(), msg.UUID) //mark this message from sender
                    if p.hasSeenPull(p.node.ID(), msg.UUID) { // check if we have received
                       //ignore
                       //fmt.Printf("skip OP_FED_COMP_PULL_REQ from %s(%s) opcode : %v\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.Opcode)
                       return nil
                    }
                    p.markSeenPull(p.node.ID(), msg.UUID) //otherwise, mark it

                    if p.hasSeenPush(p.node.ID(), msg.UUID) { // check if we have received
                       //fmt.Printf("this pullreq is new but already have item by OP_FED_COMP_PUSH from %s(%s) opcode : %v skip\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength], msg.Opcode)
                       return nil
                    }

                    if p.events.OnFedComputationPullReq != nil {
                        p.events.OnFedComputationPullReq(msg,ctx)
                    }
               }
	       break
        case Request:
               // check if we have the item
               if p.HasUUID(msg.UUID){
                    // send product
                    //fmt.Printf("recv Download Request from %s(%s). send item\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength])
                    item := p.GetItem()
                    ctx.SendMessage(DownloadMessage{UUID: msg.UUID, Contents: item.Contents})
                }else{
                    // send deny
                    //fmt.Printf("recv Download Request from %s(%s). send deny\n", ctx.ID().Address, ctx.ID().ID.String()[:printedLength])
                    ctx.SendMessage(Deny{})
                }
		break
	}//switch
	return nil
}

// peers prints out all peers we are already aware of.
func (p *Protocol) Peers_bc() {
	ids := p.Table_bc().Peers()

        var str []string
        for _, id := range ids {
	        str = append(str, fmt.Sprintf("%s(%s)", id.Address, id.ID.String()[:printedLength]))
        }

        fmt.Printf("You know %d peer(s): [%v]\n", len(ids), strings.Join(str, ", "))
}

func (p *Protocol) Peers_gr() {
	ids := p.Table_gr().Peers()

        var str []string
        for _, id := range ids {
	        str = append(str, fmt.Sprintf("%s(%s)", id.Address, id.ID.String()[:printedLength]))
        }

        fmt.Printf("You know %d peer(s): [%v]\n", len(ids), strings.Join(str, ", "))
}
/*
// callback function for Group(). User has to define the group
// TODO : default BFS 
type Group_Callback func(sublist map[string]interface{})

func (p *Protocol) Group(sublist map[string]interface{}, callback Group_Callback) {
        callback(sublist)
}
*/
