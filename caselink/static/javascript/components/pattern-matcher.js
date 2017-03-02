var alertAjax = require('../lib/ajaxHelper.js');
var _ = require('lodash');

module.exports = {
  template: "#pattern-matcher",
  data: function (){
    return {
      pattern: '',
      cases: ''
    };
  },
  methods: {
    fetchCases: _.debounce(function(pattern){
      var that = this;
      $.get('pattern-matcher/' + this.pattern)
        .done(function(data){
          if(!data.cases || data.cases.length < 1){
            that.cases = 'No matching case founded.';
          }
          that.cases = data.cases.join("<br>");
        })
        .fail(function(err){
          that.cases = 'Server Error';
        });
    },
      800),
  },
  watch: {
    pattern: function(){
      this.cases = 'Loading...';
      this.fetchCases(this.pattern);
    }
  },
  delimiters: ['${', '}'],
};
