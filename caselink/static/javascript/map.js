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
          autoDict = manualcases.reduce((a, b) => {(b.cases.reduce((x, y) => {return a[y]?a[y].count += 1: a[y] = {case: y, count: 1};}, null)); return a;}, {}),
          manualDict = manualcases.reduce(function(a, b){a[b.polarion] = b; return a;}, {}),
          autocases = d3.values(autoDict);

        let svg = d3.select("#linkage-map-svg"),
          width = +svg.attr("width"),
          height = +svg.attr("height"),
          g = svg.append("g"),
          maxLength = Math.max(manualcases.length, autocases.length),
          mRatio = manualcases.length / maxLength,
          aRatio = autocases.length / maxLength,
          mScaleX = scaleLinear().range([0, width]).domain([0, manualcases.length]),
          aScaleX = scaleLinear().range([0, width]).domain([0, maxLength]);

        var manualG = g.append("g"),
          manual = manualG.selectAll('circle')
          .data(manualcases)
          .enter()
          .append("circle")
          .attr("cy",function(d,i){d.y = 100; return d.y;})
          .attr("cx",function(d,i){d.x = mScaleX(i); return d.x;})
          .attr("fill","blue").attr("stroke","black")
          .attr("r",2);

        var autoG = g.append("g"),
          auto = autoG.selectAll('rect')
          .data(autocases)
          .enter()
          .append("circle")
          .attr("cy",function(d,i){d.y = 700; return d.y;})
          .attr("cx",function(d,i){d.x = aScaleX(i); return d.x;})
          .attr("fill","pink").attr("stroke","black")
          .attr("r",2);

        var links = manualcases.reduce((a, b) => { return a.concat(b.cases.reduce((x,y) => {x.push(
          [b.polarion, y,
            (autoDict[y].count == 1 && manualDict[b.polarion].cases.length == 1)?'s2s':
            (autoDict[y].count == 1)?'s2m':
            (manualDict[b.polarion].cases.length == 1)?'m2s':
            'm2m']
        ); return x;}, [])); }, []),
          color = {
            'm2m': 'red',
            's2s': 'black',
            's2m': 'blue',
            'm2s': 'green',
          },
          opacity = {
            'm2m': 0.25,
            's2s': 0.5,
            's2m': 0.25,
            'm2s': 0.75,
          };
        var lineG = g.append("g"),
          line = lineG.selectAll('line')
          .data(links)
          .enter()
          .append("line")
          .style("stroke", function(d){return color[d[2]];})
          .style("stroke-opacity", function(d){return opacity[d[2]];})
          .attr("x1",function(d){return manualDict[d[0]].x;})
          .attr("y1",function(d){return manualDict[d[0]].y;})
          .attr("x2",function(d){return autoDict[d[1]].x;})
          .attr("y2",function(d){return autoDict[d[1]].y;});
      });
  }
});

