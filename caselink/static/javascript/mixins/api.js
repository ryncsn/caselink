//Use a mixin to make use of bootstrap components.

module.exports = {
  methods: {
    _ajax: function(args, data){
      args.contentType = "application/json; charset=utf-8";
      if(data)
        args.data = JSON.stringify(data);
      return $.ajax(args);
    },
    _restAjax: function(method, url, data) {
      return this._ajax({method: method, url: url}, data);
    },
    _getBug: function(data) {return this._restAjax('GET', `/bug/${data.id}/`);},
    _createBug: function(data) {return this._restAjax('POST', '/bug/', data);},
    _updateBug: function(data) {return this._restAjax('PUT', `/bug/${data.id}/`, data);},
    _deleteBug: function(data) {return this._restAjax('DELETE', `/bug/${data.id}/`);},
    _getOrCreateBug: function(data) {return this._getBug(data).catch(reason => {return this._createBug(data); });},
    _getFailure: function(data) {
      if(data.id){
        return this._restAjax('GET', `/autocase_failure/${data.id}/`);
      } else if (data.failure_regex || data.autocase_pattern) {
        return this._restAjax('GET', `/autocase_failure/?failure_regex=${data.failure_regex || ''}&autocase_pattern=${data.autocase_pattern || ''}`)
          .then(res => {
            return (res.results.length != 1) ? Promise.reject(`Invalid number of result: ${res.results.length}`) : res.results[0];
          });
      } else {
            Promise.reject("Invalid query");
      }
    },
    _createFailure: function(data) {return this._restAjax('POST', '/autocase_failure/', data);},
    _updateFailure: function(data) {return this._restAjax('PUT', `/autocase_failure/${data.id}`, data);},
    _deleteFailure: function(data) {return this._restAjax('DELETE', `/autocase_failure/${data.id}`);},
    _getOrCreateFailure: function(data) {return this._getFailure(data).catch(reason => {return this._createFailure(data); });},
  },
};
