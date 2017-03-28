var dtMixins = require("datatables-mixins");
var htmlify = require('./lib/htmlify.js');
var p = require('./lib/sharedParameters.js');
var Vue = require('vue');
var navBar = require('./mixins/nav-bar.js');

var vm = new Vue({
  el: "#caselink",
  mixins: [navBar],
  data: {
    dt: null,
  },
  methods: {
    getManualCaseData: function(caseName){
      return $.get(`/data/m2a/${caseName}/`);
    },
    refreshManualCase: function(caseName){
      let workItemRowSelector = function(idx, data, node){
        return data.polarion == caseName;
      };
      let row = this.dt.row(workItemRowSelector);
      if (row.child())
        row.child().hide();
      this.getManualCaseData(caseName)
        .then(function(data){
          row.data(data.data[0]).draw();
        });
    },
  },
  watch: {},
  delimiters: ['${', '}'],
  mounted: function(){
    "use strict";
    let vm = this;
    var linkage_modal = $('#linkage_modal');
    var linkage_list_item = $('.linkage-list-item').detach();
    var maitai_automation_modal = $("#maitai_automation_modal");

    //Add listen for linkage editor
    linkage_modal.on("click", "#linkage_add_new", function(){
      var linkage_list = linkage_modal.find('#linkage_list');
      var new_item = linkage_list_item.clone();
      new_item.data('status', 'new');
      linkage_list.append(new_item);
    });

    linkage_modal.on("click", "#linkage_save", function(){
      var button = $(this);
      var promises = [];
      var deleted = linkage_modal.data('deleted');

      button.prop('disabled', true);

      for(var i = 0; i < deleted.length; i++){
        console.log({method: 'DELETE', url:'/linkage/' + deleted[i].id + "/"});
        promises.push(
          $.ajax({method: 'DELETE', url:'/linkage/' + deleted[i].id + "/"})
        );
      }

      var comment = linkage_modal.find('#workitem_comment').val(),
        workitem = linkage_modal.find('#linkage_workitem').val();

      console.log('PUT', '/workitem/' + workitem + "/", JSON.stringify({'id': workitem, 'comment': comment}));
      promises.push($.ajax({
        contentType: "application/json; charset=utf-8",
        method: 'PUT',
        url:'/workitem/' + workitem + "/",
        data: JSON.stringify({'id': workitem, 'comment': comment}),
      }));

      var items = linkage_modal.find('.linkage-list-item');

      for(let i = 0; i < items.length; i++){
        var ele = $(items[i]);
        var data = {
          workitem: workitem,
          autocase_pattern: ele.find("#linkage_pattern").val(),
          framework: ele.find("#linkage_framework").val(),
        };
        if(ele.data('status') == 'exists'){
          console.log('PUT', '/linkage/' + ele.data('linkage').id + "/", JSON.stringify(data));
          promises.push($.ajax({
            contentType: "application/json; charset=utf-8",
            method: 'PUT',
            url:'/linkage/' + ele.data('linkage').id + "/",
            data: JSON.stringify(data),
          }));
        }
        if(ele.data('status') == 'new'){
          console.log('POST', '/linkage/', JSON.stringify(data));
          promises.push($.ajax({
            contentType: "application/json; charset=utf-8",
            method: 'POST',
            url:'/linkage/',
            data: JSON.stringify(data),
          }));
        }
      }

      $.when.apply($, promises).then(function(schemas) {
        linkage_modal.modal('hide');
      }, function(e) {
        alert("Failed to save the linkage data.");
      }).always(function(){
        button.prop('disabled', false);
        vm.refreshManualCase(linkage_modal.find('#linkage_workitem').val());
      });
    });

    linkage_modal.on("click", "#linkage_delete", function(){
      var linkage_item = $(this).closest(".linkage-list-item");
      var deleted = linkage_modal.data('deleted');
      if (linkage_item.data('linkage') && linkage_item.data('linkage').id) {
        deleted.push(linkage_item.data('linkage'));
      }
      linkage_modal.data('deleted', deleted);
      linkage_item.remove();
    });

    var form = maitai_automation_modal.find('form');
    var caseInput = maitai_automation_modal.find("input[name='workitems']");
    var labelInput = maitai_automation_modal.find("input[name='labels']");
    var labelDefault = labelInput.val();

    $("#maitai_automation_submit").click(function(){
      var button = $(this);
      var posting = $.post("/control/maitai_request/", form.serialize());
      button.prop('disabled', true);
      posting.done(function(data){
        for(var polarion in data){
          vm.refreshManualCase(polarion);
          var maitai_id = data[polarion].maitai_id;
          var message = data[polarion].message;
          if(maitai_id){
            alert("Maitai create for " + polarion + ", ID: " + maitai_id);
          }
          else{
            alert('Ajax failure for ' + polarion + ': ' + data[polarion].message);
          }
        }
      }).fail(function(jqXHR, textStauts){
        try{
          var data = JSON.stringify(jqXHR.responseText);
          if(data.message){
            alert('Ajax failure: ' + data.message);
          }
          else{
            alert('Ajax failure: ' + jqXHR.responseText);
          }
        }
        catch (e){
          alert('Unknown failure, detail: ' + jqXHR.responseText);
        }
      }).always(function(){
        maitai_automation_modal.modal("hide");
        button.prop('disabled', false);
      });
    });

    vm.dt = $('#sortable-table').DataSearchTable({
      select: true,
      BaseTable: [dtMixins.DataTableWithChildRow, dtMixins.DataTableWithInlineButton, dtMixins.DataTableJumpPageButton],
      buttons: [
        {
          text: 'Select All Filted',
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
            filterSet.each(function(){
              //with select: single, only one row is processed.
              var d = vm.dt.row(this).data();
              var linkage_list = linkage_modal.find('#linkage_list').empty();
              linkage_modal.data('deleted', []);
              linkage_modal.data('row', vm.dt.row(this));
              $.get("/workitem/" + d.polarion + "/link/").done(function(data){
                $.each(data, function(idx, ele){
                  var new_item = linkage_list_item.clone();
                  new_item.find("#comment").val(ele.comment);
                  new_item.find("#linkage_pattern").val(ele.autocase_pattern);
                  new_item.find("#linkage_framework").val(ele.framework);
                  new_item.find("#linkage_autocases").html(ele.autocases.join("<br>"));
                  new_item.data('linkage', ele);
                  new_item.data('status', 'exists');
                  linkage_list.append(new_item);
                });
              });
              linkage_modal.find('#linkage_workitem').val(d.polarion).prop('disabled', true);
              linkage_modal.modal('show');
            });
          }
        },
        {
          text: 'Create Automated Request',
          action: function ( e, dt, node, config ) {
            var filterSet = vm.dt.$('tr', {selected:true});
            var checkFlag = true;
            caseInput.val('');
            labelInput.val(labelDefault);
            var count = filterSet.length;
            filterSet.each(function(){
              var row = vm.dt.row(this);
              var d = row.data();
              if(d.automation !== "notautomated"){
                alert("Create automation request for a " + d.automation + " is not allowed.");
                checkFlag = false;
                return;
              }
              if(!d.maitai_id){
                caseInput.val(caseInput.val() + " " +d.polarion);
                for(let docName of d.documents){
                  docName = docName.replace(/\ /g, "");
                  if(labelInput.val().indexOf(docName) === -1){
                    labelInput.val((labelInput.val()? labelInput.val() + "," : "") + docName);
                  }
                }
              }
              else{
                checkFlag = false;
                alert('Error: ' + d.polarion + ': Maitai pending.');
              }
              if(!--count && checkFlag){
                maitai_automation_modal.modal("show");
              }
            });
          }
        },

      ],
      initComplete: function(){
        var wi_select = $('#linkage_workitem');
        vm.dt.column(function(idx, data, node){
          return $(node).text() == 'Polarion';
        }).data().each(function(d, j){
          wi_select.append('<option value="' + d + '">' + d + '</option>');
        });

        var fr_select = linkage_list_item.find('#linkage_framework');
        $.get("/framework/").done(function(d){
          d = d.results;
          $.each(d, function(idx, d){
            fr_select.append('<option value="' + d.name + '">' + d.name + '</option>');
          });
        });
      },
      "ajax": "/data/m2a/",
      "iDisplayLength": 20,
      "bAutoWidth": false,
      "selectorColumns": [
        {
          column: 'Documents',
          render: htmlify,
        },
        {
          column: 'Automation',
          render: htmlify,
          strict: true,
        },
        {
          column: 'Errors',
          render: htmlify,
        },
      ],
      "columns": [
        {
          "data": "polarion",
          "render": function( data ) {
            return `<a href="${p.get("polarionURL")}/polarion/#/project/${p.get('polarionDefaultProject')}/workitem?id=${data}">${data}</a><br>`;
          }
        },
        { "data": "title" },
        {
          "data": "documents",
          "render": function( data ) {
            return htmlify(data.join('\n'));
          }
        },
        { "data": "automation" },
        {
          "data": "errors",
          "render": function( data ) {
            return htmlify(data.join('\n'));
          }
        },
        {
          "data": "cases",
          "visible": false,
          "render": htmlify,
        },
        {
          "data": "patterns",
          "visible": false,
          "render": htmlify,
        },
        {
          "data": "maitai_id",
          "render": htmlify,
        },
        {
          "data": "need_automation",
          "visible": false,
          "render": htmlify,
        },
        {
          "data": "comment",
          "visible": false,
          "render": htmlify,
        },
      ],

      "createdRow": function(row, data, index){
        if(data.errors.length > 0){
          $('td', row).eq(0).addClass('errors');
        }
      },

      // Add event listener for opening and closing details
      childContent: function(row, child, slideDown, slideUp){
        var childVm = new ChildRow({
          el: child.get(0),
          parent: vm,
          propsData: {
            dtData: row.data()
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

var ChildRow = Vue.extend({
  template: "#m2a-child-row",
  delimiters: ['${', '}'],
  props: ['dtData', ],
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
      for(var prop of ['autocases', 'errors', 'patterns', 'maitaiID', 'comment', 'jiraID']){
        if(this.filterEmpty(this[prop]) !== false){
          return false;
        }
      }
      return true;
    },
    jiraURL: function(){
      return `${p.get("jiraURL")}/browse/${this.jiraID}`;
    },
    autocases: function() {return this.filterEmpty(this.dtData.cases);},
    errors: function() {return this.filterEmpty(this.dtData.errors);},
    patterns: function() {return this.filterEmpty(this.dtData.patterns);} ,
    maitaiID: function(){return this.filterEmpty(this.dtData.maitai_id);},
    comment: function(){return this.filterEmpty(this.dtData.comment);},
    jiraID: function(){return this.filterEmpty(this.dtData.jira_id);},
  },
});
