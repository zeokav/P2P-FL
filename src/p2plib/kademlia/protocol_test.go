package kademlia_test

import (
	"context"
	"github.com/theued/p2plib"
	"github.com/theued/p2plib/kademlia"
	"github.com/stretchr/testify/assert"
	"go.uber.org/goleak"
	"sync"
	"testing"
)

func merge(clients ...[]*p2plib.Client) []*p2plib.Client {
	var result []*p2plib.Client

	for _, list := range clients {
		result = append(result, list...)
	}

	return result
}

func getBucketIndex(self, target p2plib.PublicKey) int {
	l := kademlia.PrefixLen(kademlia.XOR(target[:], self[:]))
	if l == p2plib.SizePublicKey*8 {
		return l - 1
	}

	return l
}

func TestTableEviction(t *testing.T) {
	defer goleak.VerifyNone(t)

	publicKeys := make([]p2plib.PublicKey, 0, kademlia.BucketSize+2)
	privateKeys := make([]p2plib.PrivateKey, 0, kademlia.BucketSize+2)

	for len(publicKeys) < cap(publicKeys) {
		pub, priv, err := p2plib.GenerateKeys(nil)
		assert.NoError(t, err)

		if len(publicKeys) < 2 {
			publicKeys = append(publicKeys, pub)
			privateKeys = append(privateKeys, priv)
			continue
		}

		actualBucket := getBucketIndex(pub, publicKeys[0])
		expectedBucket := getBucketIndex(publicKeys[1], publicKeys[0])

		if actualBucket != expectedBucket {
			continue
		}

		publicKeys = append(publicKeys, pub)
		privateKeys = append(privateKeys, priv)
	}

	leader, err := p2plib.NewNode(p2plib.WithNodePrivateKey(privateKeys[0]))
	assert.NoError(t, err)
	defer leader.Close()

	overlay := kademlia.New()
	leader.Bind(overlay.Protocol())

	assert.NoError(t, leader.Listen())

	nodes := make([]*p2plib.Node, 0, kademlia.BucketSize)

	for i := 0; i < kademlia.BucketSize; i++ {
		node, err := p2plib.NewNode(p2plib.WithNodePrivateKey(privateKeys[i+1]))
		assert.NoError(t, err)

		if i != 0 {
			defer node.Close()
		}

		node.Bind(kademlia.New().Protocol())
		assert.NoError(t, node.Listen())

		_, err = node.Ping(context.Background(), leader.Addr())
		assert.NoError(t, err)

		for _, client := range leader.Inbound() {
			client.WaitUntilReady()
		}

		nodes = append(nodes, node)
	}

	// Query all peer IDs that the leader node knows about.

	before := overlay.Table().Bucket(nodes[0].ID().ID)
	assert.Len(t, before, kademlia.BucketSize)
	assert.EqualValues(t, kademlia.BucketSize+1, overlay.Table().NumEntries())
	assert.EqualValues(t, overlay.Table().NumEntries(), len(overlay.Table().Entries()))

	// Close the node that is at the bottom of the bucket.

	nodes[0].Close()

	// Start a follower node that will ping the leader node, and cause an eviction of node 0's routing entry.

	follower, err := p2plib.NewNode(p2plib.WithNodePrivateKey(privateKeys[len(privateKeys)-1]))
	assert.NoError(t, err)
	defer follower.Close()

	follower.Bind(kademlia.New().Protocol())
	assert.NoError(t, follower.Listen())

	_, err = follower.Ping(context.Background(), leader.Addr())
	assert.NoError(t, err)

	for _, client := range leader.Inbound() {
		client.WaitUntilReady()
	}

	// Query all peer IDs that the leader node knows about again, and check that node 0 was evicted and that
	// the follower node has been put to the head of the bucket.

	after := overlay.Table().Bucket(nodes[0].ID().ID)
	assert.Len(t, after, kademlia.BucketSize)
	assert.EqualValues(t, kademlia.BucketSize+1, overlay.Table().NumEntries())
	assert.EqualValues(t, overlay.Table().NumEntries(), len(overlay.Table().Entries()))

	assert.EqualValues(t, after[0].Address, follower.Addr())
	assert.NotContains(t, after, nodes[0].ID())
}

func TestDiscoveryAcrossThreeNodes(t *testing.T) {
	defer goleak.VerifyNone(t)

	a, err := p2plib.NewNode()
	assert.NoError(t, err)
	defer a.Close()

	b, err := p2plib.NewNode()
	assert.NoError(t, err)
	defer b.Close()

	c, err := p2plib.NewNode()
	assert.NoError(t, err)
	defer c.Close()

	ka := kademlia.New()
	a.Bind(ka.Protocol())

	kb := kademlia.New()
	b.Bind(kb.Protocol())

	kc := kademlia.New()
	c.Bind(kc.Protocol())

	assert.NoError(t, a.Listen())
	assert.NoError(t, b.Listen())
	assert.NoError(t, c.Listen())

	assert.NoError(t, kb.Ping(context.TODO(), a.Addr()))

	assert.Equal(t, len(a.Inbound())+len(a.Outbound()), 1)
	assert.Equal(t, len(b.Inbound())+len(b.Outbound()), 1)
	assert.Equal(t, len(c.Inbound())+len(c.Outbound()), 0)

	assert.NoError(t, kc.Ping(context.TODO(), a.Addr()))

	assert.Equal(t, len(a.Inbound())+len(a.Outbound()), 2)
	assert.Equal(t, len(b.Inbound())+len(b.Outbound()), 1)
	assert.Equal(t, len(c.Inbound())+len(c.Outbound()), 1)

	clients := merge(a.Inbound(), a.Outbound(), b.Inbound(), b.Outbound(), c.Inbound(), c.Outbound())

	var wg sync.WaitGroup
	wg.Add(len(clients))

	for _, client := range clients {
		client := client

		go func() {
			client.WaitUntilReady()
			wg.Done()
		}()
	}

	wg.Wait()

	assert.Len(t, ka.Discover(), 2)
	assert.Len(t, kb.Discover(), 2)
	assert.Len(t, kc.Discover(), 2)
}
