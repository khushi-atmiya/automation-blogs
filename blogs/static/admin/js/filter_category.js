document.addEventListener('DOMContentLoaded', function () {
    var mainCatField = document.getElementById('id_main_category');
    var catField = document.getElementById('id_category');

    if (!mainCatField || !catField) return;

    // Badha options store karo
    var allOptions = Array.from(catField.options).map(function (o) {
        return { value: o.value, text: o.text };
    });

    function filterByMainCat(mainCatId) {
        // Pehla CATEGORIES_BY_MAIN try karo (template thi inject)
        if (window.CATEGORIES_BY_MAIN && mainCatId) {
            var filtered = window.CATEGORIES_BY_MAIN[String(mainCatId)];
            if (filtered) {
                catField.innerHTML = '<option value="">---------</option>';
                filtered.forEach(function (cat) {
                    var opt = document.createElement('option');
                    opt.value = cat.id;
                    opt.textContent = cat.name;
                    catField.appendChild(opt);
                });
                return;
            }
        }

        // Fallback: AJAX thi fetch karo
        fetch('/api/categories-by-main/' + mainCatId + '/')
            .then(function (res) { return res.json(); })
            .then(function (data) {
                catField.innerHTML = '<option value="">---------</option>';
                data.forEach(function (cat) {
                    var opt = document.createElement('option');
                    opt.value = cat.id;
                    opt.textContent = cat.name;
                    catField.appendChild(opt);
                });
            })
            .catch(function () {});
    }

    function showAll() {
        catField.innerHTML = '<option value="">---------</option>';
        allOptions.forEach(function (o) {
            if (o.value !== '') {
                var opt = document.createElement('option');
                opt.value = o.value;
                opt.textContent = o.text;
                catField.appendChild(opt);
            }
        });
    }

    // Main category change event
    mainCatField.addEventListener('change', function () {
        if (!this.value) {
            showAll();
        } else {
            filterByMainCat(this.value);
        }
    });

    // Page load par already selected hoy to filter karo
    if (mainCatField.value) {
        var existingCat = catField.value;
        filterByMainCat(mainCatField.value);
        setTimeout(function () {
            catField.value = existingCat;
        }, 300);
    }
});
