package p2plib

import (
	"container/list"
	"errors"
	"math"
	"sync"
	//"fmt"
)

type clientMapEntry struct {
	el     *list.Element
	client *Client
}

type clientMap struct {
	sync.Mutex

	cap     uint
	order   *list.List
	entries map[string]clientMapEntry
}

func newClientMap(cap uint) *clientMap {
	return &clientMap{
		cap:     cap,
		order:   list.New(),
		entries: make(map[string]clientMapEntry, cap),
	}
}

func (c *clientMap) get(n *Node, addr string) (*Client, bool) {
	c.Lock()
	defer c.Unlock()
	//fmt.Printf("try to get entries for %s\n", addr)

	entry, exists := c.entries[addr]
	if !exists {
		if uint(len(c.entries)) == n.maxInboundConnections {
		        //fmt.Printf("reach to n.maxInboundConnections\n")
			el := c.order.Back()
			evicted := c.order.Remove(el).(string)

			e := c.entries[evicted]
			delete(c.entries, evicted)
		        //fmt.Printf("close client %s\n", e.client.id.Address)

			e.client.close()
			e.client.waitUntilClosed()
		}

		//fmt.Printf("fail to get entries for %s\n", addr)
		entry.el = c.order.PushFront(addr)
		entry.client = newClient(n)

		c.entries[addr] = entry
	} else {
		c.order.MoveToFront(entry.el)
	}

	return entry.client, exists
}

func (c *clientMap) remove(addr string) {
	c.Lock()
	defer c.Unlock()

	entry, exists := c.entries[addr]
	if !exists {
		return
	}

	c.order.Remove(entry.el)
	delete(c.entries, addr)
}

func (c *clientMap) release() {
	c.Lock()

	entries := c.entries
	c.entries = make(map[string]clientMapEntry, c.cap)
	c.order.Init()

	c.Unlock()

	for _, e := range entries {
		e.client.close()
		e.client.waitUntilClosed()
	}
}

func (c *clientMap) slice() []*Client {
	c.Lock()
	defer c.Unlock()

	clients := make([]*Client, 0, len(c.entries))
	for el := c.order.Front(); el != nil; el = el.Next() {
		clients = append(clients, c.entries[el.Value.(string)].client)
	}

	return clients
}

type requestMap struct {
	sync.Mutex
	entries map[uint64]chan message
	nonce   uint64
}

func newRequestMap() *requestMap {
	return &requestMap{entries: make(map[uint64]chan message)}
}

func (r *requestMap) nextNonce() (chan message, uint64, error) {
	r.Lock()
	defer r.Unlock()

	if r.nonce == math.MaxUint64 {
		r.nonce = 0
	}

	r.nonce++
	nonce := r.nonce

	if _, exists := r.entries[nonce]; exists {
	        //fmt.Printf("entry exists\n")
		return nil, 0, errors.New("ran out of available nonce to use for making a new request")
	}

	ch := make(chan message, 1)
	r.entries[nonce] = ch
        //fmt.Printf("nonce %d registered\n",nonce)

	return ch, nonce, nil
}

func (r *requestMap) registerNonce(nonce uint64) (chan message, uint64, error) {
	r.Lock()
	defer r.Unlock()

	if _, exists := r.entries[nonce]; exists {
	        //fmt.Printf("entry exists\n")
		return nil, 0, errors.New("ran out of available nonce to use for making a new request")
	}

	ch := make(chan message, 1)
	r.entries[nonce] = ch
        //fmt.Printf("nonce %d registered\n",nonce)

	return ch, nonce, nil
}

func (r *requestMap) markRequestFailed(nonce uint64) {
	r.Lock()
	defer r.Unlock()

	close(r.entries[nonce])
	delete(r.entries, nonce)
}

func (r *requestMap) findRequest(nonce uint64) (chan message , bool){
	r.Lock()
	defer r.Unlock()

	ch, exists := r.entries[nonce]
/*
	if exists {
                fmt.Printf("nonce %d exists\n",nonce)
	}else {
                fmt.Printf("nonce %d doesn't exist\n",nonce)
	}
*/
	return ch, exists
}

func (r *requestMap) deleteRequest(nonce uint64){
	r.Lock()
	defer r.Unlock()

	delete(r.entries, nonce)
}

func (r *requestMap) close() {
	r.Lock()
	defer r.Unlock()

	for nonce := range r.entries {
		close(r.entries[nonce])
		delete(r.entries, nonce)
	}
}

//bulk message handling
type transactionMap struct {
	sync.Mutex
	entries map[string]chan message
}

func newTransactionMap() *transactionMap {
	return &transactionMap{entries: make(map[string]chan message)}
}

func (r *transactionMap) registerTransaction(id string) (chan message, error) {
	r.Lock()
	defer r.Unlock()

	if _, exists := r.entries[id]; exists {
	        //fmt.Printf("entry exists\n")
		return nil, errors.New("entry exists")
	}

	ch := make(chan message, 1)
	r.entries[id] = ch
        //fmt.Printf("ID %s registered\n",id)

	return ch, nil
}

func (r *transactionMap) findTransaction(id string) (chan message , bool){
	r.Lock()
	defer r.Unlock()

	ch, exists := r.entries[id]
/*
	if exists {
                fmt.Printf("ID %s exists\n",id)
	}else {
                fmt.Printf("ID %s doesn't exist\n",id)
	}
*/
	return ch, exists
}

func (r *transactionMap) deleteTransaction(id string){
	r.Lock()
	defer r.Unlock()

	delete(r.entries, id)
}

func (r *transactionMap) close() {
	r.Lock()
	defer r.Unlock()

	for id := range r.entries {
		close(r.entries[id])
		delete(r.entries, id)
	}
}
