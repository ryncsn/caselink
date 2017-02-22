var dtMixins = require("datatables-mixins");
var htmlify = require('./lib/htmlify.js');
var p = require('./lib/sharedParameters.js');
var Vue = require('vue');
var navBar = require('./mixins/nav-bar.js');
var _api = require('./mixins/api.js');

function _cleanEntryData() {
  return {
    id: null,
    status: '',
    bugs: [],
    description: '',
    autocase_failures: [],
    workitems: [],
  };
}

Vue.component('bl-entry-form', {
  template: "#bl-entry-form",
  mixins: [_api],
  delimiters: ['${', '}'],
  props: ['basedata', ],
  methods: {
    save: function() {
      $('#bl-entry-add-modal button').prop('disabled', true); //TODO
      let submitData = JSON.parse(JSON.stringify(this.$data));
      let failureIds = [];

      let bugsCreated = this.bugs.map(bug => {
        return this._getOrCreateBug({id: bug});
      });
      let failuresCreated = this.autocase_failures.map(failure => {
        return this._getOrCreateFailure(failure)
          .then(data => failureIds.push(data.id));
      });

      submitData.autocase_failures = failureIds;
      submitData.workitems = this.workitems.filter(s => s.length > 0);

      let op = () => {
        return (this.id) ? this._restAjax('PUT', `/blacklist/${this.id}/`, submitData) : this._restAjax('POST', `/blacklist/`, submitData);
      };
      Promise.all(bugsCreated.concat(failuresCreated)).then(op)
        .then(data => {
          this.$emit("save", data.id);
          $('#bl-entry-add-modal button').prop('disabled', false); //TODO
        })
        .catch(err => {
          alert(`Failed with ${JSON.stringify(err.responseText)}`);
          $('#bl-entry-add-modal button').prop('disabled', false); //TODO
        })
      ;
    },
    abandon: function() {
      this.$emit("abandon", null);
      this.reset();
    },
    addAutocaseFailure: function() {
      this.autocase_failures.push({
        autocases: [ ],
        autocase_pattern: "",
        failure_regex: "*"
      });
    },
    addManualCase: function() {
      this.workitems.push('');
    },
    addBug: function() {
      this.bugs.push('');
    },
    delAutocaseFailure: function(item) {
      this.autocase_failures.splice(this.autocase_failures.indexOf(item), 1);
    },
    delManualCase: function(item) {
      this.workitems.splice(this.workitems.indexOf(item), 1);
    },
    delBug: function(item) {
      this.bugs.splice(this.bugs.indexOf(item), 1);
    },
    reset: function(){
      let newData = JSON.parse(JSON.stringify(this.basedata || _cleanEntryData()));
      for (var key of ['id', 'status', 'bugs', 'description', 'autocase_failures', 'workitems']){
        this.$data[key] = newData[key];
      }
    }
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
    workitemValid: function(){
      return this.workitems.map(x => true);
    },
  },
  watch: {
    basedata: function(val){ this.reset(); },
  }
});

var vm = new Vue({
  el: "#caselink",
  mixins: [navBar, _api],
  data: {
    dt: null,
    editEntryData: {},
  },
  methods: {
    getEntryData: function(entryID){
      return $.get(`data/bl/${entryID}/`).then(data => {
        return data.data[0];
      });
    },
    refreshEntryData: function(id){
      let workItemRowSelector = function(idx, data, node){
        return data.id == id;
      };
      let row = this.dt.row(workItemRowSelector);
      if(row.data()) {
        this.getEntryData(id)
          .then(function(data){
            row.data(data).draw();
          });
      } else {
        this.getEntryData(id)
          .then(data => {
            this.dt.row.add(data);
            this.dt.draw();
          });
      }
    },
    editEntryModal: function(status, data){
      this.editEntryData = data;
      $('#bl-entry-add-modal').modal(status); //TODO
    },
    doneEditing: function(id){
      $('#bl-entry-add-modal').modal('hide'); //TODO
      if(id){
        this.refreshEntryData(id);
      }
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
        {
          text: 'Delete',
          action: function ( e, dt, node, config ) {
            var filterSet = vm.dt.$('tr', {selected:true});
            if(filterSet.length > 0){
              let check = confirm(`You are going to delete ${filterSet.length} entrys, sure?`);
              if(check){
                filterSet.each(function(entry) {
                  let row = vm.dt.row(this);
                  vm._restAjax('DELETE', `/blacklist/${row.data().id}/`)
                    .catch(err => alert(`Delete failed with ${err}`))
                    .then(_ => {row.remove(); vm.dt.draw();});
                });
              }
            }
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
        { data: "workitems", render: function( data ) { return htmlify(data.join('\n')); } },
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
