// Ensure the DOM is fully loaded before running any scripts
document.addEventListener('DOMContentLoaded', () => {
  // 1. Collapsible Section Logic
  const setupCollapsibleSections = () => {
      const buttons = document.querySelectorAll('.see-more-button');
      buttons.forEach(button => {
          const targetId = button.getAttribute('data-target');
          const section = document.getElementById(targetId);

          if (!section) {
              console.error(`Section with ID ${targetId} not found for button`, button);
              return;
          }

          button.addEventListener('click', () => {
              section.classList.remove('hidden');
              section.style.maxHeight = '0';

              setTimeout(() => {
                  section.style.transition = 'max-height 0.5s ease';
                  section.style.maxHeight = `${section.scrollHeight}px`;
              }, 10);

              setTimeout(() => {
                  button.style.display = 'none';
                  button.setAttribute('aria-expanded', 'true');
              }, 500); // Match the transition duration (0.5s)
          });

          section.addEventListener('transitionend', () => {
              section.style.maxHeight = '';
          });
      });
  };

  // 2. Swiper Navigation Logic
  const setupSwiperNavigation = () => {
      const swiperContainer = document.getElementById('swiper-container');
      const swiperLeft = document.getElementById('swiper-left');
      const swiperRight = document.getElementById('swiper-right');

      if (!swiperContainer || !swiperLeft || !swiperRight) {
          console.error('Swiper elements not found:', { swiperContainer, swiperLeft, swiperRight });
          return;
      }

      const updateButtonStates = () => {
          const scrollLeft = swiperContainer.scrollLeft;
          const maxScrollLeft = swiperContainer.scrollWidth - swiperContainer.clientWidth;

          swiperLeft.disabled = scrollLeft <= 0;
          swiperRight.disabled = scrollLeft >= maxScrollLeft;
      };

      // Calculate scroll amount dynamically based on the first item's width
      const firstItem = swiperContainer.querySelector('.swiper-item');
      const scrollAmount = firstItem ? firstItem.offsetWidth + 10 : 300; // Fallback to 300 if no items

      swiperLeft.addEventListener('click', () => {
          swiperContainer.scrollBy({
              left: -scrollAmount,
              behavior: 'smooth',
          });
      });

      swiperRight.addEventListener('click', () => {
          swiperContainer.scrollBy({
              left: scrollAmount,
              behavior: 'smooth',
          });
      });

      // Update button states on scroll
      swiperContainer.addEventListener('scroll', debounce(updateButtonStates, 100));
      updateButtonStates(); // Initial state
  };

  // 3. Debounce Function (Enhanced)
  // static/js/debounce.js
  function debounce(func, wait, immediate = false) {
    let timeout;
    return function (...args) {
        const context = this;
        const later = () => {
            timeout = null;
            if (!immediate) func.apply(context, args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func.apply(context, args);
    };
  }

  // Initialize the functionalities
  setupCollapsibleSections();
  setupSwiperNavigation();
});