(function ($) {
  "use strict";

	$(window).on('scroll', function() {
		if ($(this).scrollTop() > 200) {
			$('.scrollToTop').addClass('button-show');
		} else {
			$('.scrollToTop').removeClass('button-show');
		}
	});
  
	$(document).ready(function() {	
		$(document).on('click', '.scrollToTop, #scrollToTop', function (e) {
		   e.preventDefault();
		   e.stopPropagation();
		   try {
		     window.scrollTo({ top: 0, left: 0, behavior: 'smooth' });
		   } catch (err) {
		     window.scrollTo(0, 0);
		   }
		   document.documentElement.scrollTop = 0;
		   document.body.scrollTop = 0;
		   $("html, body").stop().animate({scrollTop: 0}, 300);
		});
	});

}(jQuery));	

