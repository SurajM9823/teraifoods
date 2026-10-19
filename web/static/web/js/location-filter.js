(function ($) {
  "use strict";

	$(document).ready(function () {
      const container = document.querySelector('.modal-location');

      if (container !== null) {
        const wrapper = container.querySelector('.search-wrapper');
        const liveSearch = () => {
          let searchQuery = container.querySelector('.location-input').value;
          const locations = container.querySelectorAll('.location-items .entry-title');

          for (var i = 0; i < locations.length; i++) {
            const self = locations[i];
            const parent = self.closest('LI');

            setTimeout(() => {
              wrapper.classList.remove('loading');
            }, 50)

            if (self.textContent.toLowerCase().includes(searchQuery.toLowerCase())) {
              parent.classList.remove("d-none");
            } else {
              parent.classList.add("d-none");
            }
          }
        }

        let typingTimer;               
        let typeInterval = 400;
        let searchInput = container.querySelector('.location-input');

        if (searchInput && wrapper) {
          searchInput.addEventListener('keyup', () => {
            clearTimeout(typingTimer);
            wrapper.classList.add('loading');
            typingTimer = setTimeout(liveSearch, typeInterval);
          });
        }
      }
	 
	  
		$('.modal-location ul .location-item > a').on( 'click', function(e) {
			e.preventDefault();
			$.cookie("location", $(this).data('slug'));
			location.reload(true); 
			/* console.log("select", e.params.data.text); */
		});
	  
		/* popup location */
		if ( !( Cookies.get( 'location' ) ) && locationfilter.popup == 1) {
			$( ".location-button" ).trigger( "click" );
		}
	  
        var str = $(".location-selector-button p").text();
        str = str.replace(/-/g, ' ');
        $(".location-selector-button p").text(str);

	
	});

})(jQuery);
