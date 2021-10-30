package graphdisp

import (
	"encoding/json"
	"fmt"
	"os"
       )

var f *os.File

type Network struct {
    Nodes []Node `json:"nodes"`
    Links []Link   `json:"links"`
}

type Node struct {
    Id string `json:"id"`
    Group int `json:"group"`
    Label string `json:"label"`
    Level int `json:"level"`
}

type Link struct {
    Source string `json:"source"`
    Target string `json:"target"`
    Strength int `json:"strength"`
}

/*
 "nodes": [
           {"id": "1", "group": 1, "label": "1", "level":2},
           {"id": "2", "group": 1, "label": "2", "level":2},
	  ],
 "links": [
           {"source": "1", "target": "2", "strength": 1.7},
           {"source": "10", "target": "9", "strength": 1.7}
          ]
*/

func FileOpen(filename string) {
    var err error
    f, err = os.OpenFile(filename, os.O_APPEND|os.O_WRONLY|os.O_CREATE, 0600)
    if err != nil {
        panic(err)
    }
}

func FileWrite(text string) {
    var err error
    if _, err = f.WriteString(text); err != nil {
        panic(err)
    }
}

func AddNode(nodes []Node, node Node) {
    nodes = append(nodes,node)
}

func AddLink(links []Link, link Link) {
    links = append(links,link)
}

func GenGraphJSON(nodes []Node, links []Link) string {
    network := Network{Nodes: nodes, Links: links}
    byteArray, err := json.MarshalIndent(network, "", "  ")
    if err != nil {
        fmt.Println(err)
    }
    fmt.Println(string(byteArray))
/*
    fileOpen("miserables.json")
    fileWrite(string(byteArray))
*/
    return string(byteArray)
}
/*
func main() {
    nodes := []Node{}
    name1 := Node{Id: "1", Group: 1, Label: "1", Level:2}
    name2 := Node{Id: "2", Group: 1, Label: "2", Level:2}
    name3 := Node{Id: "3", Group: 1, Label: "3", Level:2}
    name4 := Node{Id: "4", Group: 1, Label: "4", Level:2}
    name5 := Node{Id: "5", Group: 1, Label: "5", Level:2}
    addNode(nodes, name1)
    addNode(nodes, name2)
    addNode(nodes, name3)
    addNode(nodes, name4)
    addNode(nodes, name5)

    links := []Link{}
    name6 := Link{Source: "1", Target: "2", Strength: 1}
    name7 := Link{Source: "2", Target: "3", Strength: 1}
    name8 := Link{Source: "3", Target: "4", Strength: 1}
    name9 := Link{Source: "4", Target: "5", Strength: 1}
    name10 := Link{Source: "5", Target: "1", Strength: 1}
    addLink(links, name6)
    addLink(links, name7)
    addLink(links, name8)
    addLink(links, name9)
    addLink(links, name10)

    genGraphJSON(nodes, links)

}
*/
