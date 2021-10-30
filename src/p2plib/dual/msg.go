package dual

import (
	"fmt"
	"github.com/theued/p2plib"
	"io"
	"encoding/binary"
)

// Ping represents an empty ping message.
type Ping struct{}

// Marshal implements p2plib.Serializable and returns a nil byte slice.
func (r Ping) Marshal() []byte { return nil }

// UnmarshalPing returns a Ping instance and never throws an error.
func UnmarshalPing([]byte) (Ping, error) { return Ping{}, nil }

// Pong represents an empty pong message.
type Pong struct{}

// Marshal implements p2plib.Serializable and returns a nil byte slice.
func (r Pong) Marshal() []byte { return nil }

// UnmarshalPong returns a Pong instance and never throws an error.
func UnmarshalPong([]byte) (Pong, error) { return Pong{}, nil }

type P2pMessage struct {
      Aggregation uint32
      Opcode byte
      Contents []byte
}

func (m P2pMessage) Marshal() []byte {
      //return []byte(append([]byte{m.Opcode}, m.Contents...))
      var dst []byte
      dst = append(dst, make([]byte, 4)...)
      binary.BigEndian.PutUint32(dst[:4], m.Aggregation)
      dst = append(dst, m.Opcode)
      dst = append(dst, m.Contents...)

      return dst
}

func unmarshalP2pMessage(buf []byte) (P2pMessage, error) {
      //return P2pMessage{Opcode: buf[0], Contents: buf[1:]}, nil
      aggregation := binary.BigEndian.Uint32(buf[:4])
      opcode := buf[4]
      contents := buf[5:]

      return P2pMessage{Aggregation: aggregation, Opcode: opcode, Contents: contents}, nil
}

type DownloadMessage struct {
    UUID []byte //32bytes for plain, 34bytes for encoded
    Contents []byte
}

func (m DownloadMessage) Marshal() []byte {
    var dst []byte
    dst = append(dst, m.UUID...)
    dst = append(dst, m.Contents...)

    return dst
}

func UnmarshalDownloadMessage(buf []byte) (DownloadMessage, error) {
    uuid := buf[0:34]
    contents := buf[35:]

    return DownloadMessage{UUID: uuid, Contents: contents}, nil
}

type Request struct {
    UUID []byte //32bytes for plain, 34bytes for encoded
}

func (m Request) Marshal() []byte {
    var dst []byte
    dst = append(dst, m.UUID...)

    return dst
}

func UnmarshalRequest(buf []byte) (Request, error) {
    uuid := buf[0:34]

    return Request{UUID: uuid}, nil
}

type Deny struct{}

func (r Deny) Marshal() []byte { return nil }

func UnmarshalDeny([]byte) (Deny, error) { return Deny{}, nil }

type GossipMessage struct {
     Opcode byte
     UUID []byte //32bytes for plain, 34bytes for encoded
     Count uint32
     List []byte
     Contents []byte
}

func (m GossipMessage) Marshal() []byte {
     var dst []byte
     dst = append(dst, m.Opcode)
     dst = append(dst, m.UUID...)
     dst = append(dst, make([]byte, 4)...)
     binary.BigEndian.PutUint32(dst[35:39], m.Count)
     if m.Count != 0{
         dst = append(dst, m.List...)
     }
     dst = append(dst, m.Contents...)

     return dst
}

func UnmarshalGossipMessage(buf []byte) (GossipMessage, error) {
    var contents []byte
    var list []byte
     opcode := buf[0]
     uuid := buf[1:35]
     count := binary.BigEndian.Uint32(buf[35:39])
     if count == 0{
         contents = buf[39:]
     }else{
         list = buf[39:39+count]
         contents = buf[39+count:]
     }

     return GossipMessage{Opcode: opcode, UUID: uuid, Count: count, List: list, Contents: contents}, nil
}

// FindNodeRequest represents a FIND_NODE RPC call in the Kademlia specification. It contains a target public key to
// which a peer is supposed to respond with a slice of IDs that neighbor the target ID w.r.t. XOR distance.
type FindNodeRequest struct {
	Target p2plib.PublicKey
}

// Marshal implements p2plib.Serializable and returns the public key of the target for this search request as a
// byte slice.
func (r FindNodeRequest) Marshal() []byte {
	return r.Target[:]
}

// UnmarshalFindNodeRequest decodes buf, which must be the exact size of a public key, into a FindNodeRequest. It
// throws an io.ErrUnexpectedEOF if buf is malformed.
func UnmarshalFindNodeRequest(buf []byte) (FindNodeRequest, error) {
	if len(buf) != p2plib.SizePublicKey {
		return FindNodeRequest{}, fmt.Errorf("expected buf to be %d bytes, but got %d bytes: %w",
			p2plib.SizePublicKey, len(buf), io.ErrUnexpectedEOF,
		)
	}

	var req FindNodeRequest
	copy(req.Target[:], buf)

	return req, nil
}

// FindNodeResponse returns the results of a FIND_NODE RPC call which comprises of the IDs of peers closest to a
// target public key specified in a FindNodeRequest.
type FindNodeResponse struct {
	Results []p2plib.ID
}

// Marshal implements p2plib.Serializable and encodes the list of closest peer ID results into a byte representative
// of the length of the list, concatenated with the serialized byte representation of the peer IDs themselves.
func (r FindNodeResponse) Marshal() []byte {
	buf := []byte{byte(len(r.Results))}

	for _, result := range r.Results {
		buf = append(buf, result.Marshal()...)
	}

	return buf
}

// UnmarshalFindNodeResponse decodes buf, which is expected to encode a list of closest peer ID results, into a
// FindNodeResponse. It throws an io.ErrUnexpectedEOF if buf is malformed.
func UnmarshalFindNodeResponse(buf []byte) (FindNodeResponse, error) {
	var res FindNodeResponse

	if len(buf) < 1 {
		return res, io.ErrUnexpectedEOF
	}

	size := buf[0]
	buf = buf[1:]

	results := make([]p2plib.ID, 0, size)

	for i := 0; i < cap(results); i++ {
		id, err := p2plib.UnmarshalID(buf)
		if err != nil {
			return res, io.ErrUnexpectedEOF
		}

		results = append(results, id)
		buf = buf[id.Size():]
	}

	res.Results = results

	return res, nil
}
