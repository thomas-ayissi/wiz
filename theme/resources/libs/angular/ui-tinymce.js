'use strict';

angular.module('ui.tinymce', [])
    .constant('uiTinymceConfig', {})
    .directive('uiTinymce', uiTinymceDirective);

function uiTinymceDirective($timeout, uiTinymceConfig) {
    return {
        restrict: 'EA',
        require: '?ngModel',
        compile: function compile() {
            return postLink;
        }
    };

    function postLink(scope, iElement, iAttrs, ngModel) {
        var options = angular.extend(
            { value: iElement.text() },
            uiTinymceConfig.tinymce || {},
            scope.$eval(iAttrs.uiTinymce),
            scope.$eval(iAttrs.uiTinymceOpts)
        );

        ngModel.$render = function () {
            options.value = ngModel.$viewValue;
            ngModel.$render = function () {
                var safeViewValue = ngModel.$viewValue || '';
                newEditor(iElement, options, ngModel, scope, safeViewValue, function (editor) {
                    editor.on("change", function () {
                        var newValue = editor.getContent();
                        if (newValue !== ngModel.$viewValue) {
                            scope.$evalAsync(function () {
                                ngModel.$setViewValue(newValue);
                            });
                        }
                    });

                    scope.$on('Tinymce', function (event, callback) {
                        if (angular.isFunction(callback)) {
                            callback(editor);
                        } else {
                            throw new Error('the Tinymce event requires a callback function');
                        }
                    });

                    if (angular.isFunction(options.onLoad)) {
                        options.onLoad(editor);
                    }
                });
            };
        };
    }

    function newEditor(iElement, options, ngModel, scope, safeViewValue, cb) {
        iElement.html('');
        $(iElement).css("height", "100%");
        $(iElement).css("width", "100%");
        $(iElement).html("<textarea>" + safeViewValue + "</textarea>")
        var div = $(iElement).find("textarea")[0];
        options.target = div;
        delete options.selector
        options.setup = function (editor) {
            cb(editor);
        };

        tinymce.init(options);
    }
}
