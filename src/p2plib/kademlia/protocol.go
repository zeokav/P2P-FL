// Package kademlia is a p2plib implementation of the routing and discovery portion of the Kademlia protocol, with
// minor improvements suggested by the S/Kademlia paper.
package kademlia

import (
	"context"
	"errors"
	"fmt"
	"github.com/theued/p2plib"
	"go.uber.org/zap"
	"time"
	"strings"
)

//protocol opcode
const (
        OP_ONE_TIME  = 0x08 // node information will not be registered in routing table. one time connection
        OP_NEW_CONN  = 0x09 // it requires receivers to replace one of his routing table entry with this new node.
        OP_CONN_REQ  = 0x10 // it doesn't require receiver to replace. Simply ignore the connection req when the table is full and all entries are alive
	OP_DISCOVER  = 0x11 // discovery protocol only registers queried nodes in sender side. Receiver side doesn't register querying nodes.
)

// BucketSize returns the capacity, or the total number of peer ID entries a single routing table bucket may hold.
const BucketSize int = 16

// ErrBucketFull is returned when a routing table bucket is at max capacity.
var ErrBucketFull = errors.New("bucket is full")

// printedLength is the total prefix length of a public key associated to a chat users ID.
const printedLength = 8

// Protocol implements routing/discovery portion of the Kademlia protocol with improvements suggested by the
// S/Kademlia paper. It is expected that Protocol is bound to a p2plib.Node via (*p2plib.Node).Bind before the node
// starts listening for incoming peers.
type Protocol struct {
	node   *p2plib.Node
	logger *zap.Logger
	table  *Table

	events Events

	pingTimeout time.Duration

	maxNeighbors int
}

// New returns a new instance of the Kademlia protocol.
func New(opts ...ProtocolOption) *Protocol {

	p := &Protocol{
		pingTimeout: 3 * time.Second,
		maxNeighbors: 128,
	}

	for _, opt := range opts {
		opt(p)
	}


	return p
}

// MaxNeighbors returns cap of routing table
func (p *Protocol) MaxNeighbors() int {
        return p.maxNeighbors
}

// Find executes the FIND_NODE S/Kademlia RPC call to find the closest peers to some given target public key. It
// returns the IDs of the closest peers it finds.
func (p *Protocol) Find(target p2plib.PublicKey, opts ...IteratorOption) []p2plib.ID {
	return NewIterator(p.node, p.table, opts...).Find(target)
}

// Discover attempts to discover new peers to your node through peers your node  already knows about by calling
// the FIND_NODE S/Kademlia RPC call with your nodes ID.
func (p *Protocol) DiscoverTarget(target p2plib.PublicKey, opts ...IteratorOption) []p2plib.ID {
        return p.Find(p.node.ID().ID, opts...)
}

// Discover attempts to discover new peers to your node through peers your node  already knows about by calling
// the FIND_NODE S/Kademlia RPC call with your nodes ID.
func (p *Protocol) DiscoverRandom(opts ...IteratorOption) []p2plib.ID {
        pub, _, _ := p2plib.GenerateKeys(nil)
        return p.Find(pub, opts...)
}

// Ping sends a ping request to addr, and returns no error if a pong is received back before ctx has expired/was
// cancelled. It also throws an error if the connection to addr intermittently drops, or if handshaking with addr
// should there be no live connection to addr yet fails.
func (p *Protocol) Ping(ctx context.Context, addr string) error {
	msg, err := p.node.RequestMessage(ctx, addr, Ping{})
	if err != nil {
		return fmt.Errorf("failed to ping: %w", err)
	}

	if _, ok := msg.(Pong); !ok {
		return errors.New("did not get a pong back")
	}

	return nil
}

// Table returns this Kademlia overlay's routing table from your nodes perspective.
func (p *Protocol) Table() *Table {
	return p.table
}

func (p *Protocol) RemoveConn(id p2plib.ID) {
	    if  p.table.Recorded(id.ID) {
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
	            if entryid, deleted := p.table.Delete(id.ID); deleted {
		        fmt.Printf("Peer %s(%s) is deleted from routing table\n",
			    entryid.Address,
			    entryid.ID.String()[:printedLength],
		        )
		        if p.events.OnPeerEvicted != nil {
			        fmt.Printf("RemoveConn() bread1\n")
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
	    if  p.table.Recorded(id.ID) == false {
                //fmt.Printf("%s(%s) is not registered yet. Register first.\n",id.Address, id.ID.String()[:printedLength])
		inserted, err := p.table.Update(id)
		if err == nil {
			if inserted {
				p.logger.Debug("Peer was inserted into routing table.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
				)
			}
		}
		/*
		//debug log
	        for _, en := range p.table.Entries() {
                    fmt.Println(en)
	        }
		*/
	    }

	    entries := p.table.Peers()
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
func (p *Protocol) Ack(id p2plib.ID, opcode ...byte) {
        //fmt.Printf("Ack called %d %d\n",p.table.size, p.maxNeighbors)
        if p.table.size > p.maxNeighbors {
	    /*
	    for _, en := range p.table.Entries() {
                fmt.Println(en)
	    }
	    */
            if len(opcode) != 0 && opcode[0] == byte(OP_NEW_CONN) {
                //fmt.Printf("NEW_CONN %s %s\n",id.Address, id.ID.String()[:printedLength])
                p.ReplaceConn(id) // register current conn req and delete one of the existing one
	    }
	    // otherwise, just ignore conn req because table already reaches to maxNeighbors
	    return
        }

	for {
		inserted, err := p.table.Update(id)
		if err == nil {
			if inserted {
				p.logger.Debug("Peer was inserted into routing table.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
				)
			}

			if inserted {
				if p.events.OnPeerAdmitted != nil {
					p.events.OnPeerAdmitted(id)
				}
			} else {
				if p.events.OnPeerActivity != nil {
					p.events.OnPeerActivity(id)
				}
			}

			return
		}

		last := p.table.Last(id.ID)

		ctx, cancel := context.WithTimeout(context.Background(), p.pingTimeout)
		pong, err := p.node.RequestMessage(ctx, last.Address, Ping{})
		cancel()

		if err != nil {
			if id, deleted := p.table.Delete(last.ID); deleted {
			    /*
				p.logger.Debug("Peer was evicted from routing table by failing to be pinged.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
					zap.Error(err),
				)
*/
				fmt.Printf("Peer was evicted from routing table by failing to be pinged\n peer_addr %s\n.",id.Address)
				if p.events.OnPeerEvicted != nil {
				        fmt.Printf("Ack() bread1\n")
					p.events.OnPeerEvicted(id)
				}
			}
			continue
		}

		if _, ok := pong.(Pong); !ok {
			if id, deleted := p.table.Delete(last.ID); deleted {
				p.logger.Debug("Peer was evicted from routing table by failing to be pinged.",
					zap.String("peer_id", id.String()),
					zap.String("peer_addr", id.Address),
					zap.Error(err),
				)

				if p.events.OnPeerEvicted != nil {
				        fmt.Printf("Ack() bread2\n")
					p.events.OnPeerEvicted(id)
				}
			}
			continue
		}

		p.logger.Debug("Peer failed to be inserted into routing table as it's intended bucket is full.",
			zap.String("peer_id", id.String()),
			zap.String("peer_addr", id.Address),
		)

		if p.events.OnPeerEvicted != nil {
		        fmt.Printf("Ack() bread3\n")
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
		OnPeerDisconnected: p.OnPeerDisconnected,
		OnPingFailed:    p.OnPingFailed,
		OnMessageSent:   p.OnMessageSent,
		OnMessageRecv:   p.OnMessageRecv,
	}
}

// Bind registers messages Ping, Pong, FindNodeRequest, FindNodeResponse, and handles them by registering the
// (*Protocol).Handle Handler.
func (p *Protocol) Bind(node *p2plib.Node) error {
	p.node = node
	p.table = NewTable(p.node.ID())

	if p.logger == nil {
		p.logger = p.node.Logger()
	}

	node.RegisterMessage(Ping{}, UnmarshalPing)
	node.RegisterMessage(Pong{}, UnmarshalPong)
	node.RegisterMessage(FindNodeRequest{}, UnmarshalFindNodeRequest)
	node.RegisterMessage(FindNodeResponse{}, UnmarshalFindNodeResponse)

	node.Handle(p.Handle)

	return nil
}

// OnPeerConnected attempts to acknowledge the new peers existence by placing its entry into your nodes' routing table
// via (*Protocol).Ack
func (p *Protocol) OnPeerConnected(isInbound bool, client *p2plib.Client, opcode ...byte) {
        if len(opcode) != 0 && opcode[0] == byte(OP_ONE_TIME) {
            //fmt.Printf("One time message without registering in routing table\n")
	    return
        }

	if len(opcode) != 0 && opcode[0] == byte(OP_DISCOVER) && !isInbound {
	    fmt.Printf("we don't register incoming querying nodes\n")
	    return
	}

        //fmt.Println(p.table.Entries())
	p.Ack(client.ID(), opcode...)
	return
}

func (p *Protocol) OnPeerDisconnected(client *p2plib.Client) {
        p.RemoveConn(client.ID())
}

// OnPingFailed evicts peers that your node has failed to dial.
func (p *Protocol) OnPingFailed(addr string, err error) {
	if id, deleted := p.table.DeleteByAddress(addr); deleted {
		//p.logger.Debug("Peer was evicted from routing table by failing to be dialed.", zap.Error(err))
		fmt.Printf("Peer was evicted from routing table by failing to be dialed.", zap.Error(err))

		if p.events.OnPeerEvicted != nil {
			p.events.OnPeerEvicted(id)
		}
	}
}

// OnMessageSent implements p2plib.Protocol and attempts to push the position in which the clients ID resides in
// your nodes' routing table's to the head of the bucket it reside within.
func (p *Protocol) OnMessageSent(client *p2plib.Client, opcode ...byte) {
        if len(opcode) != 0 && opcode[0] == byte(OP_ONE_TIME) {
            //fmt.Printf("One time message without registering in routing table\n")
        }else{
	    p.Ack(client.ID())
	}
}

// OnMessageRecv implements p2plib.Protocol and attempts to push the position in which the clients ID resides in
// your nodes' routing table's to the head of the bucket it reside within.
func (p *Protocol) OnMessageRecv(client *p2plib.Client, opcode ...byte) {
        if len(opcode) != 0 && opcode[0] == byte(OP_ONE_TIME) {
            //fmt.Printf("One time message without registering in routing table\n")
        }else{
	    p.Ack(client.ID())
	}
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
		return ctx.SendMessage(FindNodeResponse{Results: p.table.FindClosest(msg.Target, BucketSize)})
	}

	return nil
}

// peers prints out all peers we are already aware of.
func (p *Protocol) Peers() {
        ids := p.Table().Peers()

        var str []string
        for _, id := range ids {
            str = append(str, fmt.Sprintf("%s(%s)", id.Address, id.ID.String()[:printedLength]))
        }

        fmt.Printf("You know %d peer(s): [%v]\n", len(ids), strings.Join(str, ", "))
}
