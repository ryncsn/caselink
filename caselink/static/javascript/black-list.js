var dtMixins = require("datatables-mixins");
var htmlify = require('./lib/htmlify.js');
var p = require('./lib/sharedParameters.js');
var Vue = require('vue');
var navBar = require('./mixins/nav-bar.js');

function _cleanEntryData() {
  return {
    status: '',
    bugs: [],
    description: '',
    autocase_failures: [],
    manualcases: [],
  };
}

Vue.component('bl-entry-form', {
  template: "#bl-entry-form",
  delimiters: ['${', '}'],
  props: ['data', ],
  methods: {
    save: function() {
    },
    abandon: function() {
    },
    addAutocaseFailure: function() {
      this.autocase_failures.push({
        autocases: [ ],
        autocase_pattern: "",
        failure_regex: "*"
      });
    },
    addManualCase: function() {
      this.manualcases.push('');
    },
    addBug: function() {
      this.bugs.push('');
    },
    delAutocaseFailure: function(item) {
      this.autocase_failures.splice(this.autocase_failures.indexOf(item), 1);
    },
    delManualCase: function(item) {
      this.manualcases.splice(this.manualcases.indexOf(item), 1);
    },
    delBug: function(item) {
      this.bugs.splice(this.bugs.indexOf(item), 1);
    },
  },
  data: function() {
    return _cleanEntryData();
  },
  computed: {
    statusValid: function(){
      return this.status in ['bug', 'bug-skip', 'case-update', 'case-update-skip', 'bug-wont-fix'];
    },
    bugsURL: function(){
      return this.bugs.map(bug => `${bugzillaURL}/${bug}`);
    },
    bugsValid: function(){
      return this.bugs.map(bug => true);
    },
    autocasesValid: function(){
      return this.autocases_failures.map(x => true);
    },
    manualcaseValid: function(){
      return this.manualcases.map(x => true);
    },
  },
  watch: {
    data: function(val){
      console.log("Change");
      for (var key of ['status', 'bugs', 'description', 'autocase_failures', 'manualcases']){
        this[key] = (this.data || _cleanEntryData())[key];
      }
    },
  }
});

var vm = new Vue({
  el: "#caselink",
  mixins: [navBar],
  data: {
    dt: null,
    editEntryData: {},
  },
  methods: {
    getEntryData: function(entryID){
      return $.get(`?pk=${caseName}`);
    },
    refreshEntryData: function(caseName){
      let manualCaseRowSelector = function(idx, data, node){
        return data.polarion == caseName;
      };
      let row = this.dt.row(manualCaseRowSelector);
      this.getManualCaseData(caseName)
        .then(function(data){
          row.data(data.data[0]).draw();
        });
    },
    editEntryModal: function(status, data){
      this.editEntryData = data;
      $('#bl-entry-add-modal').modal(status); //TODO
    }
  },
  delimiters: ['${', '}'],
  mounted: function(){
    "use strict";
    let vm = this;
    vm.dt = $('#sortable-table').DataSearchTable({
      select: true,
      BaseTable: [dtMixins.DataTableWithChildRow, dtMixins.DataTableWithInlineButton, dtMixins.DataTableJumpPageButton],
      buttons: [
        {
          text: 'Select All Filtered',
          action: function ( e, dt, node, config ) {
            var filterSet = vm.dt.$('tr', {filter:'applied'});
            filterSet.each(function(){
              vm.dt.row(this).select();
            });
          }
        },
        {
          text: 'Edit',
          action: function ( e, dt, node, config ) {
            var filterSet = vm.dt.$('tr', {selected:true});
            if(filterSet.length > 1){
              alert("Linkage edit with multi-select is not supported yet.");
              return;
            }
            filterSet.each(function(row){
              vm.editEntryModal('show', vm.dt.row(this).data());
            });
          }
        },
        {
          text: 'Add New Entry',
          action: function ( e, dt, node, config ) {
            vm.editEntryModal('show', null);
          }
        },
      ],
      initComplete: function(){
      },
      ajax: "data/bl/",
      iDisplayLength: 20,
      bAutoWidth: false,
      selectorColumns: [
        { column: 'Errors', render: htmlify, },
      ],
      columns: [
        { data: "status", },
        { data: "description", render: function( data ) { return htmlify(data); } },
        { data: "bugs", render: function( data ) { return htmlify(data.join('\n')); } },
        { data: "manualcases", render: function( data ) { return htmlify(data.join('\n')); } },
        { data: "autocase_failures", render: function( data ) { return htmlify(data.map(d=>d.autocases.join('\n')).join('\n')); } },
        { data: "errors", render: function( data ) { return htmlify(data.join('\n')); } },
      ],

      createdRow: function(row, data, index){
        if(data.errors.length > 0){ $('td', row).eq(0).addClass('errors'); }
      },

      // Add event listener for opening and closing details
      childContent: function(row, child, slideDown, slideUp){
        var childVm = new EntryChildRow({
          el: child.get(0),
          parent: vm,
          propsData: {
            data: row.data()
          },
          mounted: function(){
            slideDown();
            if(this.empty){
              setTimeout(slideUp, 800);
            }
          },
        });
      },
    });
  },
});

var EntryChildRow = Vue.extend({
  template: "#bl-entry-child-row",
  delimiters: ['${', '}'],
  props: ['data', ],
  methods: {
    filterEmpty: function(value) {
      return value !== null && Object.keys(value).length !== 0 && value;
    },
  },
  data: function() {
    return {};
  },
  computed: {
    empty: function(){
      return !this.filterEmpty(this.data.autocase_failures);
    },
    autocase_failures: function(){
      return this.data.autocase_failures;
    },
  },
});
