//Helper for sharing some parameters between template and frontend framework
(function (root, factory) {
  if (typeof root !== 'object'){
    throw new Error("Not supported enviroment");
  }
  if (typeof define === 'function' && define.amd) {
    define(['exports'], function (exports) {
      factory((root.sharedParameters = exports));
    });
  } else if (typeof exports === 'object' && typeof exports.nodeName !== 'string') {
    factory(exports);
  } else {
    factory((root.sharedParameters = {}));
  }
}(this || window, function (exports) {
  exports._sharedParameters = exports._sharedParameters || {};
  exports.set = function(name, value){
    exports._sharedParameters[name] = value;
  };
  exports.get = function(name){
    return exports._sharedParameters[name];
  };
}));
