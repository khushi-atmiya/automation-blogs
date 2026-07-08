document.addEventListener('DOMContentLoaded', function () {
    var catField = document.getElementById('id_category');
    var mainCatsField = document.getElementById('id_main_categories');

    if (!catField || !mainCatsField) return;

    function autoSelectMainCats(catId) {
        if (!catId) return;
        if (window.MAINS_BY_CATEGORY) {
            var mainCatIds = window.MAINS_BY_CATEGORY[String(catId)];
            if (mainCatIds) {
                Array.from(mainCatsField.options).forEach(function (option) {
                    option.selected = mainCatIds.includes(parseInt(option.value));
                });
                var event = new Event('change', { bubbles: true });
                mainCatsField.dispatchEvent(event);
            }
        }
    }

    // Category change event to auto-select main categories
    catField.addEventListener('change', function () {
        autoSelectMainCats(this.value);
    });

    // Auto-select on page load for new objects (where no main categories are selected yet)
    var isAnySelected = Array.from(mainCatsField.options).some(function(o) { return o.selected; });
    if (catField.value && !isAnySelected) {
        autoSelectMainCats(catField.value);
    }
});
