(function ($) {
  "use strict";
	
	$(document).ready(function() {
		
		// The static storefront owns cart state through its .open classes.
		// Do not also attach the legacy GSAP controller to these same buttons.
		if (document.querySelector('script[src*="terai-interactive.js"]')) return;

		this.body = document.body;
		
		const container = document.querySelector('.cart-widget-side');
      
		if (container !== null) {
			const button = document.querySelectorAll('.mini-cart-button');
			const close = container.querySelector('.cart-side-close');
			const overlay = document.querySelector('.cart-side-overlay');

			let tl = gsap.timeline( { paused: true, reversed: true } );
			tl.set( container, {
			  autoAlpha: 1
			}).to( container, .5, {
			  x:0,
			  ease: 'power4.inOut'
			}).to( overlay, .5, {
			  autoAlpha: 0.6,
			  ease: 'power4.inOut'
			}, "-=.5");

			if (button !== null) {
				for( var i = 0; i < button.length; i++ ) {
					const self = button[i];
		  
					  self.addEventListener('click', (e) => {
						e.preventDefault();
						this.body.classList.add('cart-widget-side-active');
						tl.reversed() ? tl.play() : tl.reverse();
					  }, false);
			  
				}
			}

			$( document.body ).on( 'added_to_cart', function() {
				$(".quick-button.mini-cart-button").trigger("click");

			});

			overlay.addEventListener('click', (e) => {
			  e.preventDefault();
			  this.body.classList.remove('cart-widget-side-active');
			  tl.reverse();
			})

			close.addEventListener('click', (e) => {
			  e.preventDefault();
			  this.body.classList.remove('cart-widget-side-active');
			  tl.reverse();
			})
			
		}
		
     
	  
	  $('.mini-cart-holder').remove();
	  
	});

})(jQuery);
