import { Component, OnInit } from '@angular/core';
import { ViewEncapsulation } from '@angular/core'

declare var Treant: any;

@Component({
  encapsulation: ViewEncapsulation.None,
  selector: 'app-nodeviz',
  templateUrl: './nodeviz.component.html',
  styleUrls: ['./nodeviz.component.css']
})
export class NodevizComponent implements OnInit {

  constructor() { }

  config = {
    container: "#treant-id"
  };

  // [[0], [0:0, 4:0], [0:0, 1:0, 2:0, 3:0, 4:1]]
  create_tree_visualization(branching_factor: number, nodes_list: Array<number>): any{
    var nodes: any[] = [[{text: {name: nodes_list[0].toString()}}]];

    var current_round = 0;
    var num_of_rounds = Math.ceil(Math.log(nodes_list.length)/Math.log(branching_factor))
    console.log(nodes)
    console.log(num_of_rounds)
    while(num_of_rounds-current_round){
      let cur_mod = Math.pow(branching_factor,num_of_rounds-current_round-1)
      console.log("current_mod" + cur_mod.toString())
      var parent_idx = 0
      var cur_nodes: any[] =[]
      nodes_list.forEach(
        (val, ind, arr) => {
          if (ind % cur_mod == 0) {
            cur_nodes.push({
              parent: nodes[current_round][Math.floor(ind/(cur_mod*branching_factor))],
              text: {name: val.toString()}
            });

          }
        }
      )
      nodes.push(cur_nodes);
      current_round+=1;
      console.log(nodes)
    }
    console.log(nodes.flat())
    return nodes.flat();
  };

  ngOnInit() {
    // this.create_tree_visualization(2, [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    this.create_tree_visualization(4, [0, 1, 2, 3, 4]);
    (() => {Treant([this.config].concat(this.create_tree_visualization(4, [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10])))})();
  }

  // ngOnInit(): void {
  //
  // }

}
