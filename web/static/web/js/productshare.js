(function ($) {
  "use strict";

	$(document).on('groginShopPageInit', function () {
		groginThemeModule.productshare();
	});

	groginThemeModule.productshare = function() {
      const shareButton = document.querySelector('.single-product-wrapper .share-button > a');
      const socialHolder = document.querySelector('.share-buttons-holder');

      if (socialHolder !== null) {
        const urlHolder = socialHolder.querySelector('.site-url');
        const urlText = urlHolder.querySelector('.url').innerHTML;
        const copyText = urlHolder.querySelector('.copy-text .copy');
        const copiedText = urlHolder.querySelector('.copy-text .copied');
        const closeButton = socialHolder.querySelector('.close-button');
        const urlHolderOverlay = socialHolder.querySelector('.share-buttons-overlay');

        const copyContent = async() => {
          try {
            await navigator.clipboard.writeText(urlText);
            copyText.classList.add('d-none');
            copiedText.classList.remove('d-none');
            setTimeout(() => {
              copyText.classList.remove('d-none');
              copiedText.classList.add('d-none');
            }, 700)
          } catch (err) {
            console.error('Failed to copy: ', err);
          }
        }

        urlHolder.addEventListener('click', copyContent);

        if (shareButton !== null) {
          shareButton.addEventListener('click', (e) => {
            e.preventDefault();
            socialHolder.classList.add('active');
            this.body.classList.add('share-buttons-active');
          })
        }

        [closeButton, urlHolderOverlay].forEach((button) => {
          button.addEventListener('click', (e) => {
            e.preventDefault();
            socialHolder.classList.remove('active');
            this.body.classList.remove('share-buttons-active');
          })
        })
      }
	}
	$(document).ready(function() {
		groginThemeModule.productshare();
	});

})(jQuery);
