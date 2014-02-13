ratbot = (function() {
    var my = {};

    my.confirm_delete = function(event) {
        if ($(event.target).find('input#delete:checked').length) {
            if (! window.confirm('Are you sure you want to delete this?')) {
                event.preventDefault();
                return false;
            }
        }
    };

    return my;
})();
