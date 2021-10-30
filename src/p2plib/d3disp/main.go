package main

import (
	"encoding/json"
	"fmt"
	"os"
	"praphdisp"
       )

func main() {
    nodes := []grapdisp.Node{}
    name1 := grapdisp.Node{Id: "1", Group: 1, Label: "1", Level:2}
    name2 := grapdisp.Node{Id: "2", Group: 1, Label: "2", Level:2}
    name3 := grapdisp.Node{Id: "3", Group: 1, Label: "3", Level:2}
    name4 := grapdisp.Node{Id: "4", Group: 1, Label: "4", Level:2}
    name5 := grapdisp.Node{Id: "5", Group: 1, Label: "5", Level:2}
    grapdisp.AddNode(nodes, name1)
    grapdisp.AddNode(nodes, name2)
    grapdisp.AddNode(nodes, name3)
    grapdisp.AddNode(nodes, name4)
    grapdisp.AddNode(nodes, name5)

    links := []grapdisp.Link{}
    name6 := grapdisp.Link{Source: "1", Target: "2", Strength: 1}
    name7 := grapdisp.Link{Source: "2", Target: "3", Strength: 1}
    name8 := grapdisp.Link{Source: "3", Target: "4", Strength: 1}
    name9 := grapdisp.Link{Source: "4", Target: "5", Strength: 1}
    name10 := grapdisp.Link{Source: "5", Target: "1", Strength: 1}
    grapdisp.AddLink(links, name6)
    grapdisp.AddLink(links, name7)
    grapdisp.AddLink(links, name8)
    grapdisp.AddLink(links, name9)
    grapdisp.AddLink(links, name10)

    grapdisp.GenGraphJSON(nodes, links)

}
