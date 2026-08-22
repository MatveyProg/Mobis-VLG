(function () {
  'use strict';

  const sidebar = document.getElementById('sidebar');
  const menuBtn = document.getElementById('menuBtn');
  const sidebarClose = document.getElementById('sidebarClose');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  function openSidebar() {
    if (!sidebar) return;
    sidebar.classList.add('is-open');
    document.body.classList.add('no-scroll');
  }

  function closeSidebar() {
    if (!sidebar) return;
    sidebar.classList.remove('is-open');
    document.body.classList.remove('no-scroll');
  }

  if (menuBtn) menuBtn.addEventListener('click', openSidebar);
  if (sidebarClose) sidebarClose.addEventListener('click', closeSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sidebar && sidebar.classList.contains('is-open')) {
      closeSidebar();
    }
  });

  const carousel = document.getElementById('productCarousel');
  const prevBtn = document.getElementById('carouselPrev');
  const nextBtn = document.getElementById('carouselNext');

  if (carousel && prevBtn && nextBtn) {
    const scrollAmount = 296;
    prevBtn.addEventListener('click', function () {
      carousel.scrollBy({ left: -scrollAmount, behavior: 'smooth' });
    });
    nextBtn.addEventListener('click', function () {
      carousel.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    });
  }

  const makeSelect = document.getElementById('vehicleMake');
  const modelSelect = document.getElementById('vehicleModel');

  function initVehiclePicker() {
    const carModelsEl = document.getElementById('car-models-data');
    if (!makeSelect || !modelSelect || !carModelsEl) return;

    const carModels = JSON.parse(carModelsEl.textContent);

    function populateModels(makeId) {
      modelSelect.innerHTML = '<option value="">Модель</option>';
      if (!makeId) {
        modelSelect.disabled = true;
        return;
      }
      carModels
        .filter(function (model) { return String(model.make_id) === String(makeId); })
        .forEach(function (model) {
          const option = document.createElement('option');
          option.value = model.id;
          option.textContent = model.name;
          modelSelect.appendChild(option);
        });
      modelSelect.disabled = modelSelect.options.length <= 1;
    }

    makeSelect.addEventListener('change', function () {
      populateModels(makeSelect.value);
    });

    if (makeSelect.value) {
      populateModels(makeSelect.value);
    }
  }

  initVehiclePicker();

  const vehicleForm = document.getElementById('vehicleForm');
  if (vehicleForm && makeSelect) {
    vehicleForm.addEventListener('submit', function (e) {
      if (!makeSelect.value) {
        e.preventDefault();
      }
    });
  }
})();
