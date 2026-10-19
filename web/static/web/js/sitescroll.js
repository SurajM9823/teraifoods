(function ($) {
  "use strict";

	$(document).on('groginShopPageInit', function () {
		groginThemeModule.sitescroll();
	});

	groginThemeModule.sitescroll = function() {
		const container = document.querySelectorAll('.site-scroll');

		if (container !== null) {
			for( var i = 0; i < container.length; i++ ) {
			  const self = container[i];

			  if ($(self).hasScrollBar()) {
				self.classList.add('scrollbar-active');
			  }
			}
		}
	}
	
	$(document).ready(function() {
		groginThemeModule.sitescroll();
	});

})(jQuery);
