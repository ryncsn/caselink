var d3 = require('d3');
var scaleLinear = require('d3-scale').scaleLinear;
var Vue = require('vue');
var p = require('./lib/sharedParameters.js');
var navBar = require('./mixins/nav-bar.js');

var vm = new Vue({
  el: "#linkage-map",
  mixins: [navBar],
  data: {},
  methods: {},
  watch: {},
  delimiters: ['${', '}'],
  mounted: function(){
    $.get("data?type=m2a")
      .done(function(data){
        let manualcases = data.data.filter((a) => {return a.cases.length > 0;}),
          autocases = manualcases.reduce((a, b) => { return a.concat(b.cases.reduce((x, y) => { x.push({case: y}); return x; }, [])); }, []),
          manualDict = manualcases.reduce(function(a, b){a[b.polarion] = b; return a;}, {}),
          autoDict = autocases.reduce(function(a, b){a[b.case] = b; return a;}, {});

        let svg = d3.select("#linkage-map-svg"),
          width = +svg.attr("width"),
          height = +svg.attr("height"),
          g = svg.append("g"),
          scaleX = scaleLinear().range([0, width]).domain([0, Math.max(manualcases.length, autocases.length)]);

        var manualG = g.append("g"),
          manual = manualG.selectAll('circle')
          .data(manualcases)
          .enter()
          .append("circle")
          .attr("cy",function(d,i){d.y = 100; return d.y;})
          .attr("cx",function(d,i){d.x = scaleX(i); return d.x;})
          .attr("fill","blue").attr("stroke","black")
          .attr("r",2);

        var autoG = g.append("g"),
          auto = autoG.selectAll('rect')
          .data(autocases)
          .enter()
          .append("circle")
          .attr("cy",function(d,i){d.y = 700; return d.y;})
          .attr("cx",function(d,i){d.x = scaleX(i); return d.x;})
          .attr("fill","pink").attr("stroke","black")
          .attr("r",2);

        var links = manualcases.reduce((a, b) => { return a.concat(b.cases.reduce((x,y) => {x.push([b.polarion, y]); return x;}, [])); }, []);
        var lineG = g.append("g"),
          line = lineG.selectAll('line')
          .data(links)
          .enter()
          .append("line")
          .style("stroke", function(d){return 'black';})
          .style("stroke-opacity", function(d){return 0.03;})
          .attr("x1",function(d){return manualDict[d[0]].x;})
          .attr("y1",function(d){return manualDict[d[0]].y;})
          .attr("x2",function(d){return autoDict[d[1]].x;})
          .attr("y2",function(d){return autoDict[d[1]].y;});
      });
  }
});

