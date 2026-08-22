(function () {
  'use strict';

  /* ------------------------------------------------------------------
     Mobile sidebar
  ------------------------------------------------------------------ */
  const sidebar = document.getElementById('sidebar');
  const menuBtn = document.getElementById('menuBtn');
  const sidebarClose = document.getElementById('sidebarClose');
  const sidebarOverlay = document.getElementById('sidebarOverlay');

  function openSidebar() {
    sidebar.classList.add('is-open');
    document.body.classList.add('no-scroll');
  }

  function closeSidebar() {
    sidebar.classList.remove('is-open');
    document.body.classList.remove('no-scroll');
  }

  if (menuBtn) menuBtn.addEventListener('click', openSidebar);
  if (sidebarClose) sidebarClose.addEventListener('click', closeSidebar);
  if (sidebarOverlay) sidebarOverlay.addEventListener('click', closeSidebar);

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && sidebar.classList.contains('is-open')) {
      closeSidebar();
    }
  });

  /* ------------------------------------------------------------------
     Product carousel (desktop)
  ------------------------------------------------------------------ */
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

  /* ------------------------------------------------------------------
     Favorites toggle
  ------------------------------------------------------------------ */
  document.querySelectorAll('[data-favorite]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();
      e.stopPropagation();
      btn.classList.toggle('is-active');

      var svg = btn.querySelector('svg');
      if (svg) {
        svg.setAttribute('fill', btn.classList.contains('is-active') ? 'currentColor' : 'none');
      }
    });
  });

  /* ------------------------------------------------------------------
     Add to cart feedback
  ------------------------------------------------------------------ */
  document.querySelectorAll('[data-add-cart]').forEach(function (btn) {
    btn.addEventListener('click', function (e) {
      e.preventDefault();

      var badge = document.querySelector('.header__badge[data-cart-count]');
      if (badge) {
        var count = parseInt(badge.textContent, 10) || 0;
        badge.textContent = count + 1;
      }

      btn.style.transform = 'scale(0.9)';
      setTimeout(function () {
        btn.style.transform = '';
      }, 150);
    });
  });

  /* ------------------------------------------------------------------
     Vehicle picker form
  ------------------------------------------------------------------ */
  var vehicleForm = document.getElementById('vehicleForm');
  if (vehicleForm) {
    vehicleForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var make = vehicleForm.querySelector('[name="make"]').value;
      var model = vehicleForm.querySelector('[name="model"]').value;
      if (make && model) {
        window.location.href = '#catalog?make=' + encodeURIComponent(make) + '&model=' + encodeURIComponent(model);
      }
    });
  }

  var vinForm = document.getElementById('vinForm');
  if (vinForm) {
    vinForm.addEventListener('submit', function (e) {
      e.preventDefault();
      var vin = vinForm.querySelector('[name="vin"]').value.trim();
      if (vin.length >= 11) {
        window.location.href = '#catalog?vin=' + encodeURIComponent(vin);
      }
    });
  }

  /* ------------------------------------------------------------------
     Bottom nav active state
  ------------------------------------------------------------------ */
  document.querySelectorAll('.bottom-nav__item').forEach(function (item) {
    item.addEventListener('click', function (e) {
      document.querySelectorAll('.bottom-nav__item').forEach(function (el) {
        el.classList.remove('is-active');
      });
      item.classList.add('is-active');
    });
  });
})();
