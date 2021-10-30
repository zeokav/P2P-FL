package p2plib_test

import (
	"encoding/hex"
	"encoding/json"
	"github.com/oasisprotocol/ed25519"
	"github.com/theued/p2plib"
	"github.com/stretchr/testify/assert"
	"testing"
)

func TestMarshalJSON(t *testing.T) {
	pub, priv, err := ed25519.GenerateKey(nil)
	assert.NoError(t, err)

	var pubKey p2plib.PublicKey
	var privKey p2plib.PrivateKey

	copy(pubKey[:], pub)
	copy(privKey[:], priv)

	pubKeyJSON, err := json.Marshal(pubKey)
	assert.NoError(t, err)

	privKeyJSON, err := json.Marshal(privKey)
	assert.NoError(t, err)

	assert.Equal(t, "\""+hex.EncodeToString(pub)+"\"", string(pubKeyJSON))
	assert.Equal(t, "\""+hex.EncodeToString(priv)+"\"", string(privKeyJSON))
}
