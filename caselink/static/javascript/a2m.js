var dtMixins = require("datatables-mixins");
var htmlify = require('./lib/htmlify.js');
var p = require('./lib/sharedParameters.js');
var Vue = require('vue');
var navBar = require('./mixins/nav-bar.js');

var vm = new Vue({
  el: "#caselink",
  mixins: [navBar],
  data: {},
  methods: {},
  watch: {},
  delimiters: ['${', '}'],
});

$(document).ready(function() {
  "use strict";
  var table = $('#sortable-table').DataSearchTable( {
    BaseTable: [dtMixins.DataTableJumpPageButton],
    "ajax": "data?type=a2m",
    "iDisplayLength": 20,
    "bAutoWidth": false,
    "selectorColumns": [
      {
        column: 'Component',
        render: htmlify,
        strict: true,
      },
      {
        column: 'Framework',
        render: htmlify,
        strict: true,
      },
      {
        column: 'Documents',
        render: htmlify,
      },
      {
        column: 'PR',
        render: htmlify,
      },
      {
        column: 'Errors',
        render: htmlify,
      }
    ],
    "columns": [
      { "data": "case" },
      {
        "data": "polarion",
        "render": function(data) {
          var link = "";
          for (var i in data){
            var polarionId = data[i];
            link += `<a href="${p.get("polarionURL")}/polarion/#/project/${p.get('polarionDefaultProject')}/workitem?id=${polarionId}">${polarionId}</a><br>`;
          }
          return link;
        }
      },
      {
        "data": "title",
        "render": function(data){
          return htmlify(data.join('\n'));
        }
      },
      {
        "data": "documents",
        "render": function(data){
          return htmlify(data.join('\n'));
        }
      },
      {
        "data": "components",
        "render": function(data){
          return htmlify(data.join('\n'));
        }
      },
      {
        "data": "framework",
      },
      {
        "data": "pr",
        "render":  htmlify
      },
      {
        "data": "errors",
        "render": function(data){
          return htmlify(data.join('\n'));
        }
      },
    ],
    "createdRow": function (row, data, index){
      if (data.errors.length > 0) {
        $('td', row).eq(0).addClass('errors');
      }
    }
  });
});

