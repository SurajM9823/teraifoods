(function ($) {
  "use strict";

	$(document).on('groginShopPageInit', function () {
		groginThemeModule.siteslider();
	});

	groginThemeModule.siteslider = function() {
		const container = document.querySelectorAll('.site-slider');

		if (container !== null) {
			for( var i = 0; i < container.length; i++ ) {
			  const self = container[i];

			  let slide_items = Number(self.dataset.items);
			  let slide_itemsTablet = Number(self.dataset.itemstablet);
			  let slide_itemsMobile = Number(self.dataset.itemsmobile);
			  let slide_itemSlide = Number(self.dataset.itemscroll) ? Number(self.dataset.itemscroll) : 1;
			  let slide_speed = Number(self.dataset.speed);
			  let slide_arrows = self.dataset.arrows === 'true' ? true : false;
			  let slide_dots = self.dataset.dots === 'true' ? true : false;
			  let slide_infinite = self.dataset.infinite === 'true' ? true : false;
			  let slide_asNavFor = self.dataset.assfor_nav;
			  let slide_focusOnSelect = self.dataset.focuson_select === 'true' ? true : false;
			  let slide_autoplay = self.dataset.autoplay === 'true' ? true : false;
			  let slide_autoSpeed = Number(self.dataset.auto_speed);
			  let slide_css = self.dataset.css;
			  let slide_rtl = self.dataset.rtl === 'true' ? true : false;
			  let slide_vertical = self.dataset.vertical === 'true' ? true : false;
			  let slide_draggable = self.dataset.draggable === 'true' ? true : false;
			  let slide_adaptiveHeight = self.dataset.adaptiveheight === 'true' ? true : false;

			  let args = {
				arrows: slide_arrows,
				dots: slide_dots,
				slidesToShow: slide_items,
				slidesToScroll: slide_itemSlide,
				speed: slide_speed,
				infinite: slide_infinite,
				asNavFor: slide_asNavFor,
				focusOnSelect: slide_focusOnSelect,
				autoplay: slide_autoplay,
				autoplaySpeed: slide_autoSpeed,
				cssEase: slide_css,
				lazyLoad: 'ondemand',
				rtl: slide_rtl,
				vertical: slide_vertical,
				variableWidth: false,
				prevArrow: '<button type="button" class="slick-nav slick-prev slick-button"><svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" viewBox="0 0 24 24" enable-background="new 0 0 24 24" fill="currentColor"><polyline fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="17.2,22.4 6.8,12 17.2,1.6 "/></svg></button>',
				nextArrow: '<button type="button" class="slick-nav slick-next slick-button"><svg xmlns="http://www.w3.org/2000/svg" x="0px" y="0px" viewBox="0 0 24 24" enable-background="new 0 0 24 24" fill="currentColor"><polyline fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" points="6.8,22.4 17.2,12 6.8,1.6 "/></svg></button>',
				touchThreshold: 100,
				draggable: slide_draggable,
				adaptiveHeight: slide_adaptiveHeight,
				rows: 0,
				responsive: [
				  {
					breakpoint: 1280,
					settings: {
					  slidesToShow: slide_itemsTablet ? slide_itemsTablet : (slide_items <= 4 ? slide_items : 3)
					}
				  }, {
					breakpoint: 1200,
					settings: {
					  slidesToShow: slide_itemsTablet ? slide_itemsTablet : (slide_items <= 4 ? slide_items : 3)
					}
				  }, {
					breakpoint: 1024,
					settings: {
					  slidesToShow: slide_itemsTablet ? slide_itemsTablet : (slide_items <= 4 ? slide_items : 3)
					}
				  }, {
					breakpoint: 576,
					settings: {
					  slidesToShow: slide_itemsMobile ? slide_itemsMobile : (slide_items <= 3 ? slide_items : 2),
					  slidesToScroll: slide_itemsMobile ? slide_itemsMobile : (slide_items <= 3 ? slide_items : 2),
					  dots: self.classList.contains('carousel-style') ? slide_dots === false ? true : true : slide_dots,
					}
				  }
				]
			  };

			  $(self).not('.slick-initialized').slick( args );
			}
		}
	}
	
	$(document).ready(function() {
		groginThemeModule.siteslider();
	});

})(jQuery);
