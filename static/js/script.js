const buttonSee = document.getElementById('buttonsee');
const section2 = document.getElementById('seclect2');

buttonSee.addEventListener('click', () => {
    section2.classList.remove('hidden');
    section2.style.maxHeight = '0'; 

    setTimeout(() => {
        section2.style.transition = 'max-height 0.5s ease';
        section2.style.maxHeight = section2.scrollHeight + 'px';
    }, 10);

    setTimeout(() => {
        buttonSee.style.display = 'none';
    }, 100); 
});

section2.addEventListener('transitionend', () => {
    section2.style.maxHeight = '';
});

// my code

document.addEventListener('DOMContentLoaded', () => {
    const swiperContainer = document.getElementById('swiper-container');
    const swiperLeft = document.getElementById('swiper-left');
    const swiperRight = document.getElementById('swiper-right');
  
    swiperLeft.addEventListener('click', () => {
      swiperContainer.scrollBy({
        left: -300, // Adjust the scroll amount as needed
        behavior: 'smooth',
      });
    });
  
    swiperRight.addEventListener('click', () => {
      swiperContainer.scrollBy({
        left: 300, // Adjust the scroll amount as needed
        behavior: 'smooth',
      });
    });
  });
