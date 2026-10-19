(function ($) {
  "use strict";

  const GROGIN_SITE = {
    init() {
      this.dom();
      this.themeCategoriesMenu();
      this.themeHeaderCategoriesHolder();
      this.themeSearchOverlay();
      this.themeModalSelector();
      this.themeDrawerAnimation();
      this.themeMobileMenu();
      this.themeMyAccountMenu();
      this.minicartmobile();
	  this.themeCategoriesDrawer();
    },
    dom() {
      this.body = document.body;
      this.drawerMenu = document.querySelector('.site-menu-drawer');
      // Header selectors
      const header = document.querySelector('.site-header');
      const gliobalNotification = document.querySelector('.global-notification');
      // Mobile navbar selector
      const mobileNavbar = document.querySelector('.site-mobile-navbar');

      // Controls the scrollbar
      $.fn.hasScrollBar = function() {
        return this.get(0).scrollHeight > this.height();
      }

      // Set header height
      const setHeaderHeight = () => {
        if (gliobalNotification !== null) {
          return header.clientHeight + gliobalNotification.clientHeight;
        }
        return header.clientHeight;
      }
      window.addEventListener("load", setHeaderHeight);
      window.addEventListener("resize", setHeaderHeight);
      
      // Get header height
      const getHeaderHeight = () => {
        const getHeagederHeightItem = document.querySelectorAll('.get-header-height');
        if (getHeagederHeightItem !== null || header !== null) {
          for( var i = 0; i < getHeagederHeightItem.length; i++ ) {
            getHeagederHeightItem[i].style.setProperty('--header-height', `${setHeaderHeight()}px`);
          }
        }
      }
      window.addEventListener("load", getHeaderHeight);
      window.addEventListener("resize", getHeaderHeight);

      // Site on scroll 
      const onScroll = () => {
        const scroll = document.documentElement.scrollTop;

        if (scroll > setHeaderHeight()) {
          this.body.classList.add('site-has-scroll');
        } else {
          this.body.classList.remove('site-has-scroll');
        }
      }

      window.addEventListener('scroll', onScroll)

      // Set mobile navbar height
      const setMobileNavbar = () => {
        if (mobileNavbar !== null) {
          return mobileNavbar.clientHeight;
        }
      }
      window.addEventListener("load", setMobileNavbar);
      window.addEventListener("resize", setMobileNavbar);

      // Get mobile navbar height
      const getMobileNavHeight = () => {
        const getMobileNavHeightItem = document.querySelectorAll('.get-mobile-nav-height');
        if (getMobileNavHeightItem !== null || mobileNavbar !== null) {
          for( var i = 0; i < getMobileNavHeightItem.length; i++ ) {
            if (getMobileNavHeightItem[i].getAttribute("style")) {
              getMobileNavHeightItem[i].style.cssText = `${getMobileNavHeightItem[i].getAttribute("style")} --mobile-nav-height: ${setMobileNavbar()}px`;
            } else {
              getMobileNavHeightItem[i].style.cssText = `--mobile-nav-height: ${setMobileNavbar()}px`;
            }
          }
        }
      }
      window.addEventListener("load", getMobileNavHeight);
      window.addEventListener("resize", getMobileNavHeight);
    },
    themeCategoriesMenu() {
      const header = document.querySelector('.site-header');
      const container = header.querySelectorAll('.categories-menu');

      if (container !== null) {
        for ( var i = 0; i < container.length; i++ ) {
          const self = container[i];
          const menu = self.querySelector('#category-menu');

          if (menu !== null) {
            const hasChildMenu = menu.querySelectorAll( '.menu-item-has-children' );
            for (var i = 0; i < hasChildMenu.length; i++) {
              const hasItem = hasChildMenu[i];
              const subMenu = hasItem.lastElementChild;

              if (subMenu.classList.contains('sub-menu')) {
                const subParent = subMenu.parentNode;

                if ( subParent.classList.contains( 'has-image' ) ) {
                  const menuWidth = subMenu.offsetWidth;

                  subMenu.style.width = menuWidth + ( menuWidth / 1.5 ) + 'px';
                }

                hasItem.addEventListener('mouseover', (e) => {
                  header.classList.add('category-menu-hover');
                })
        
                hasItem.addEventListener('mouseleave', (e) => {
                  header.classList.remove('category-menu-hover');
                })
              }
            }
          }
        }
      }
    },
    themeHeaderCategoriesHolder() {
      const header = document.querySelector('.site-header');
      const container = header.querySelector('.header-categories-holder');

      if (container !== null) {
        const categoriesMenu = container.querySelector('.site-categories');
        const button = document.querySelector('.categories-button');
        const categoriesClose = container.querySelector('.close-button');
        const categoriesOverlay = container.querySelector('.categories-holder-overlay');
        const hasChild = categoriesMenu ? categoriesMenu.querySelectorAll('.menu-item-has-children') : [];

        if (hasChild && hasChild.length !== 0) {

          hasChild[0].classList.add('focus');

          for ( var i = 0; i < hasChild.length; i++ ) {
            const self = hasChild[i];

            self.addEventListener('mouseover', (e) => {
              self.classList.add('active');
            })
    
            self.addEventListener('mouseleave', (e) => {
              self.classList.remove('active');
            })
          }
        }

        if (button !== null) {
          button.addEventListener('click', (e) => {
            e.preventDefault();
            container.classList.add('active');
          })
        }

        if (categoriesClose !== null || categoriesOverlay !== null) {
          [categoriesClose, categoriesOverlay].forEach((element) => {
            element.addEventListener('click', (e) => {
              e.preventDefault();
              container.classList.remove('active');
            })
         });
        }
      }
    },
    themeSearchOverlay() {
      const header = document.querySelector('.site-header');
      const container = header.querySelectorAll('.search-overlay');

      if (container !== null) {
        for( var i = 0; i < container.length; i++ ) {
          const self = container[i];
          const input = self.querySelector( '.search-input' );

          input.addEventListener('focus', () => {
            self.classList.add( 'is-searchable' );
            header.classList.add( 'search-overlay-focus' );
          })

          input.addEventListener('blur', () => {
            setTimeout(() => {
              self.classList.remove( 'is-searchable' );
              header.classList.remove( 'search-overlay-focus' );
            }, 100);
          })
        }
      }
    },
    themeModalSelector() {
      const modalButton = document.querySelectorAll('.modal-button');

      if (modalButton !== null) {
        for( var i = 0; i < modalButton.length; i++ ) {
          const self = modalButton[i];
          const modalName = self.dataset.modal;
          const currentModal = document.getElementById(modalName);
          const closeModal = currentModal.querySelector('.close-button');
          const modalOverlay = currentModal.querySelector('.site-modal-overlay');

          self.addEventListener('click', (e) => {
            e.preventDefault();
            currentModal.classList.add('active');
          })

          if (closeModal !== null || modalOverlay !== null) {
            [closeModal, modalOverlay].forEach((element) => {
              element.addEventListener('click', (e) => {
                e.preventDefault();
                currentModal.classList.remove('active');
              })
           });
          }
        }
      }
    },

    themeDrawerAnimation() {
      const buttons = document.querySelectorAll('.menu-drawer-toggle');
      const drawers = new Map();
      let activeDrawer = null;
      const clearButtons = () => {
        this.body.classList.remove('site-menu-drawer-active', 'site-categories-drawer-active', 'site-search-drawer-active');
        buttons.forEach(button => button.classList.remove('active'));
      };
      const closeDrawer = () => {
        clearButtons();
        if (activeDrawer) drawers.get(activeDrawer).reverse();
        activeDrawer = null;
      };
      buttons.forEach(button => {
        const name = button.dataset.drawer;
        const item = document.querySelector(`.${name}`);
        if (!item) return;
        if (!drawers.has(item)) {
          const inner = item.querySelector('.site-drawer-inner');
          const overlay = item.querySelector('.site-drawer-overlay');
          const timeline = gsap.timeline({ paused: true });
          timeline.fromTo(item, .1, { autoAlpha: 0 }, { autoAlpha: 1 })
            .to(inner, .5, { x: 0, ease: 'power4.inOut' }, 0)
            .to(overlay, .5, { autoAlpha: 1, ease: 'power4.inOut' }, 0);
          drawers.set(item, timeline);
          item.querySelectorAll('.close-button, .site-drawer-overlay').forEach(close => {
            close.addEventListener('click', event => {
              event.preventDefault();
              closeDrawer();
            });
          });
        }
        button.addEventListener('click', event => {
          event.preventDefault();
          const wasOpen = activeDrawer === item;
          closeDrawer();
          if (!wasOpen) {
            activeDrawer = item;
            drawers.get(item).play();
            button.classList.add('active');
            this.body.classList.add(`${name}-active`);
          }
        });
      });
      document.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeDrawer();
      });
      window.addEventListener('pageshow', event => {
        if (event.persisted) closeDrawer();
      });
    },
    themeMobileMenu() {
      if (this.drawerMenu !== null) {
        const hasChildren = this.drawerMenu.querySelectorAll( '.menu-item-has-children' );
        const subMenu = ( e ) => {
          let subUl;
          if ( e.target.tagName === 'A' ) {
            e.preventDefault();
            subUl = e.target.nextElementSibling;
          } else {
            subUl = e.target.previousElementSibling;
          }
          let parentUl = e.target.closest( 'ul' );
          let parentLi = e.target.closest( 'li' );
          let activeLi = parentUl.querySelectorAll( '.menu-item-has-children.active' );

          const closeSubs = () => {
            for ( var i = 0; i < activeLi.length; i++ ) {
              const activeSub = activeLi[i].children[1];
              const childSubs = activeSub.querySelectorAll( '.sub-menu' );
              for ( var i = 0; i < childSubs.length; i++ ) {
                if ( childSubs[i] != null ) {
                  gsap.set( childSubs[i], { height: 0 } );
                }
              }
            }
          }

          const subAnimation = ( element, event ) => {
            gsap.to( element, { duration: .4, height: event, ease: 'power4.inOut', onComplete: closeSubs } );
          }

          if ( !parentLi.classList.contains( 'active' ) ) {
            for ( var i = 0; i < activeLi.length; i++ ) {
              activeLi[i].classList.remove( 'active' );
              const sub = activeLi[i].children[1];
              subAnimation( sub, 0 );
            }
            parentLi.classList.add( 'active' );
            subAnimation( subUl, 'auto' );
          } else {
            parentLi.classList.remove( 'active' );
            subAnimation( subUl, 0 );
          }

        }

        for( var i = 0; i < hasChildren.length; i++ ) {
          const dropdown = document.createElement( 'span' );
          dropdown.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" class="feather feather-chevron-down"><polyline points="6 9 12 15 18 9"></polyline></svg>';
          dropdown.className = 'menu-dropdown';
          hasChildren[i].appendChild( dropdown );

          const link = hasChildren[i].querySelector( 'a[href*="#"]' );
          const sub = hasChildren[i].children[1];
          gsap.set( sub, { height: 0 } );
          dropdown.addEventListener( 'click', subMenu );
		  if (link !== null) {
          link.addEventListener( 'click', subMenu );
		  }
        }
      }
    },
    themeMyAccountMenu() {
      const button = document.querySelector('.user-menu-toggle a');
      const accountMenu = document.querySelector('.my-account-navigation');

      if (button !== null || accountMenu !== null) {
        button.addEventListener('click', (e) => {
          e.preventDefault();
          accountMenu.classList.toggle('active');
        })
      }
    },

    minicartmobile() {
	  if($(window).width() < 601){
		  var button = $( '.site-header .mini-cart-button > a.action-link' );

		  button.on( 'click', function(e) {
			e.preventDefault();
			if($( '.site-header .mini-cart-button .mini-cart-holder' ).hasClass('hide')){
				$( '.site-header .mini-cart-button .mini-cart-holder' ).removeClass( 'hide' );
			} else {
				$( '.site-header .mini-cart-button .mini-cart-holder' ).addClass( 'hide' );
			}
		  });
	  }
    },

    themeCategoriesDrawer() {
      const container = document.querySelector('.site-categories-drawer');

      if (container !== null) {
        const subMenu = container.querySelectorAll(".menu-item-has-children");
        if (subMenu !== null) {
          for ( var i = 0; i < subMenu.length; i++ ) {
            const self = subMenu[i];

			const subMenuLink = self.querySelector(':scope > a');
            subMenuLink.addEventListener('click', (event) => {
              event.preventDefault();
              if (event.target.closest('LI').classList.contains('active')) {
                event.target.closest('LI').classList.remove("active");
              } else {
                (container.querySelector('.menu-item-has-children.active')) ? container.querySelector('.menu-item-has-children.active').classList.remove('active') : '';
                event.target.closest('LI').classList.toggle("active");
              }
            });
          }
        }
      }
    }

  }

  GROGIN_SITE.init();
  
	$(document).ready(function() {
		var $header = $('header.site-header');
		var $cat = $('.categories-menu .site-categories');
		var $toggle = $('.categories-menu a.categories-toggle');
		var $banner = $('.site-slider, .site-banner');
		var isHomePage = $('body').hasClass('home') && $banner.length > 0;
		var manuallyOpened = false;
		var fullCatHeight = 524;

		function getFullHeight() {
			if ($(window).scrollTop() === 0 && $banner.length && $toggle.length) {
				var bRect = $banner[0].getBoundingClientRect();
				var tRect = $toggle[0].getBoundingClientRect();
				var measured = Math.round(bRect.bottom - tRect.bottom);
				if (measured > 300) {
					fullCatHeight = measured;
				}
			}
			return fullCatHeight;
		}

		var ticking = false;

		function handleStickyAndCategories() {
			var scrollTop = $(window).scrollTop();
			var isDesktop = window.innerWidth >= 1200;

			// 1. Sticky header with hysteresis gap to eliminate jitter/blinking near top
			if (scrollTop > 80) {
				if (!$header.hasClass('sticky-header')) {
					$header.addClass('sticky-header');
				}
			} else if (scrollTop <= 10) {
				if ($header.hasClass('sticky-header')) {
					$header.removeClass('sticky-header');
				}
			}

			// If not desktop home page with hero banner, fallback to standard collapse behavior
			if (!isHomePage || !isDesktop) {
				var vh = window.innerHeight || $(window).height();
				if (scrollTop >= vh) {
					if ($cat.hasClass('show')) {
						$cat.collapse('hide');
					}
				}
				return;
			}

			// 2. Home Page: Contract categories in lockstep with the hero banner on scroll
			var bRect = $banner[0].getBoundingClientRect();
			var tRect = $toggle[0].getBoundingClientRect();
			var remaining = Math.round(bRect.bottom - tRect.bottom);
			var fullH = getFullHeight();

			// When scrolling back up into banner zone, re-attach to banner tracking
			if (remaining > 0 && manuallyOpened) {
				manuallyOpened = false;
			}

			if (manuallyOpened) {
				return; // preserve manually opened state while scrolled past banner
			}

			if (remaining >= fullH - 2) {
				// At top: fully expanded, bottom aligned with banner bottom, overflow visible for flyout submenus
				$cat[0].style.setProperty('display', 'flex', 'important');
				$cat[0].style.setProperty('height', fullH + 'px', 'important');
				$cat[0].style.setProperty('max-height', fullH + 'px', 'important');
				$cat[0].style.setProperty('overflow', 'visible', 'important');
				$cat.addClass('show').removeClass('collapsed');
			} else if (remaining > 0) {
				// Scrolling down/up through banner: smoothly contracts/expands so bottom follows banner bottom
				$cat[0].style.setProperty('display', 'flex', 'important');
				$cat[0].style.setProperty('height', remaining + 'px', 'important');
				$cat[0].style.setProperty('max-height', remaining + 'px', 'important');
				$cat[0].style.setProperty('overflow', 'hidden', 'important');
				$cat.addClass('show').removeClass('collapsed');
			} else {
				// Scrolled past hero banner: fully collapsed
				$cat[0].style.setProperty('display', 'none', 'important');
				$cat[0].style.setProperty('height', '0px', 'important');
				$cat[0].style.setProperty('max-height', '0px', 'important');
				$cat[0].style.setProperty('overflow', 'hidden', 'important');
				$cat.removeClass('show').addClass('collapsed');
			}
		}

		function onScroll() {
			if (!ticking) {
				ticking = true;
				window.requestAnimationFrame(function () {
					handleStickyAndCategories();
					ticking = false;
				});
			}
		}

		// Collapsible toggle behavior on click
		$toggle.on('click', function (e) {
			e.preventDefault();
			e.stopPropagation();

			if (!isHomePage || window.innerWidth < 1200) {
				$cat.collapse('toggle');
				return;
			}

			var bRect = $banner[0].getBoundingClientRect();
			var tRect = $toggle[0].getBoundingClientRect();
			var remaining = Math.round(bRect.bottom - tRect.bottom);
			var fullH = getFullHeight();

			// If scrolled past banner or currently collapsed: toggle as standard dropdown
			if (remaining <= 0 || $cat.hasClass('collapsed') || $cat.is(':hidden')) {
				manuallyOpened = !manuallyOpened;
				if (manuallyOpened) {
					$cat[0].style.setProperty('display', 'flex', 'important');
					$cat[0].style.setProperty('height', fullH + 'px', 'important');
					$cat[0].style.setProperty('max-height', fullH + 'px', 'important');
					$cat[0].style.setProperty('overflow', 'visible', 'important');
					$cat[0].style.setProperty('box-shadow', '0 15px 35px rgba(0,0,0,0.15)', 'important');
					$cat.addClass('show').removeClass('collapsed');
				} else {
					$cat[0].style.setProperty('display', 'none', 'important');
					$cat[0].style.setProperty('height', '0px', 'important');
					$cat[0].style.setProperty('max-height', '0px', 'important');
					$cat.removeClass('show').addClass('collapsed');
				}
			} else {
				// At top: allow manual collapse/expand
				if ($cat.is(':visible')) {
					$cat[0].style.setProperty('display', 'none', 'important');
					$cat[0].style.setProperty('height', '0px', 'important');
					$cat[0].style.setProperty('max-height', '0px', 'important');
					$cat.removeClass('show').addClass('collapsed');
				} else {
					$cat[0].style.setProperty('display', 'flex', 'important');
					$cat[0].style.setProperty('height', fullH + 'px', 'important');
					$cat[0].style.setProperty('max-height', fullH + 'px', 'important');
					$cat[0].style.setProperty('overflow', 'visible', 'important');
					$cat.addClass('show').removeClass('collapsed');
				}
			}
		});

		// Close manually opened dropdown on outside click
		$(document).on('click', function(e) {
			if (isHomePage && manuallyOpened) {
				if (!$(e.target).closest('.categories-menu').length) {
					manuallyOpened = false;
					handleStickyAndCategories();
				}
			}
		});

		$(window).on('scroll', onScroll);
		$(window).on('resize', function() {
			getFullHeight();
			handleStickyAndCategories();
		});

		// Initial precision alignment
		setTimeout(function() {
			getFullHeight();
			handleStickyAndCategories();
		}, 100);
		setTimeout(function() {
			getFullHeight();
			handleStickyAndCategories();
		}, 500);
		setTimeout(function() {
			getFullHeight();
			handleStickyAndCategories();
		}, 1200);
	});
	
	$(window).on('load', function(){
		$('.site-loading').fadeOut('slow',function(){$(this).remove();});
	});
	
}(jQuery));
