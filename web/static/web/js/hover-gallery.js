class HoverGallery {
  constructor(option) {
    this.mm = gsap.matchMedia();
    this.selector = option.selector;
    this.selectorWrapper = document.createElement('DIV');
    this.selectorInner = document.createElement('DIV');
    this.slides = gsap.utils.toArray(this.selector.querySelectorAll(':scope > *'));
    //this.slides = gsap.utils.toArray(this.selector.children);
    //this.slides = gsap.utils.toArray(this.selector.querySelectorAll('.product-gallery-item'));
    //this.slides = this.selector.querySelectorAll('.product-gallery-item');
    this.slidesLength = this.slides.length;
    this.slideDuration = option.duration ? option.duration : 0.3;
    this.resetHover = option.resetHover;
    this.progressPerItem = 1 / (this.slidesLength - 1);
    this.threshold = this.progressPerItem / 5;
    this.snapProgress = gsap.utils.snap(this.progressPerItem)
    this.slideWidth = 0;
    this.totalWidth = 0;
    this.currentIndex = 0;

    window.addEventListener('resize', function (event) {
      this.resizeSlider();
    }.bind(this));

    this.animation = gsap.to(this.slides, 1, {
      xPercent: "-=" + (this.slidesLength - 1) * 100,
      ease: "none",
      paused: true
    })

    this.draggable = new Draggable(document.createElement('DIV'), {
      trigger: this.selectorInner,
      onPress: this.setOnPress,
      onDrag: this.setOnDrag,
      onRelease: this.animateSlides,
    });

    this.init( () => {
      this.resizeSlider();
      this.createHoverBlocks();
    });
  }

  // Init gallery
  init(el) {
    const promises = [];
    const { selector, selectorWrapper, selectorInner, slides, slidesLength } = this;

    if (slidesLength > 1) {
      slides[0].classList.add('active');
      selector.classList.add('product-gallery-images');

      const wrap = (el, wrapper, classNames = null, dots = false) => {
        el.parentNode.insertBefore(wrapper, el);
        if (classNames !== null) {
          wrapper.classList.add(classNames);
        }
        wrapper.appendChild(el);
        if (dots) {
          this.createDots();
        }
      }

      wrap(selector, selectorInner, 'product-gallery-inner', false);
      wrap(selectorInner, selectorWrapper, 'product-gallery-wrapper', true);
    }

    Promise.all( promises ).then( () => {
      el();
    });
  }

  // Create gallery dots
  createDots() {
    const { slides, selectorWrapper } = this;
    // Create dots wrapper
    let dotsFragment = document.createDocumentFragment();
    const dotsWrapper = document.createElement('DIV');
    dotsWrapper.classList.add('product-gallery-dots');

    // Create dots
    for (var i = 0; i < slides.length; i++) {
      let dot = dotsWrapper.appendChild(document.createElement('DIV'));
      dot.classList.add('dot');
      selectorWrapper.appendChild(dotsWrapper);
    }

    if (!dotsFragment) {
      selectorWrapper.appendChild(dotsFragment);
    }

    dotsWrapper.querySelectorAll(':scope > *')[0].classList.add('active');
  }

  // Change active class
  changeActiveClass(index) {
    const dots = this.selectorWrapper.querySelectorAll('.product-gallery-dots .dot');
    
    [...dots, ...this.slides].forEach((item) => {
      item.classList.remove('active');
    })
    
    dots[index].classList.add('active');
    this.slides[index].classList.add('active');
  }

  // Animation slides
  animateSlides = () => {
    gsap.to(this.animation, this.slideDuration, {
      progress: this.snapProgressDirectional(
        this.animation.progress(),
        this.draggable.deltaX > 0 ? 1 : -1
      ),
      overwrite: true,
      onComplete: () => {
        const slideProgress = Math.floor(this.animation.progress() * this.slidesLength);
        if (this.currentIndex !== slideProgress) {
          this.currentIndex = slideProgress === this.slidesLength ? slideProgress - 1 : slideProgress;
          this.changeActiveClass(this.currentIndex);
        }
      }
    })
  }

  // Draggable set on drag function
  setOnDrag = () => {
    let change = (this.draggable.startX - this.draggable.x) / this.totalWidth;
    this.animation.progress(this.draggable.startProgress + change)
  }

  // Draggable set on press function
  setOnPress = () => {
    gsap.killTweensOf(this.animation);
    this.draggable.startProgress = this.animation.progress();
  }

  // Snap progress directional
  snapProgressDirectional(value, direction) {
    let snapped = this.snapProgress(value);

    if (direction < 0 && value - snapped > this.threshold) {
      return snapped + this.progressPerItem;
    } else if (direction > 0 && snapped - value > this.threshold) {
      return snapped - this.progressPerItem;
    }

    return snapped;
  }

  // Hover gallery blocks for desktop
  createHoverBlocks() {
    const { slides, slidesLength, selectorWrapper } = this;
    if (slidesLength > 1) {
      // Create hover gallery wrapper
      let blockFragment = document.createDocumentFragment();
      const hoverGalleryWrapper = document.createElement('DIV');
      hoverGalleryWrapper.classList.add('hover-gallery-wrapper');

      // Create dots
      for (var i = 0; i < slides.length; i++) {
        let block = hoverGalleryWrapper.appendChild(document.createElement('DIV'));
        block.classList.add('hover-block');
        selectorWrapper.appendChild(hoverGalleryWrapper);
      }

      if (!blockFragment) {
        selectorWrapper.appendChild(blockFragment);
      }

      hoverGalleryWrapper.querySelectorAll(':scope > *')[this.currentIndex].classList.add('active');
      this.slideHoverBlocks(hoverGalleryWrapper);
    }
  }

  slideHoverBlocks(wrapper) {
    this.mm.add("(min-width: 1200px)", () => {
      const blocks = wrapper.querySelectorAll('.hover-gallery-wrapper .hover-block');

      const removeClass = () => {
        blocks.forEach((block) => {
          block.classList.remove('active');
        })
      }

      const over = (e) => {
        this.currentIndex = Array.prototype.slice.call(wrapper.children).indexOf( e.target );
        removeClass();
        e.target.classList.add('active');
        this.changeActiveClass(this.currentIndex);
      }

      const leave = (e) => {
        this.currentIndex = this.currentIndex;
        removeClass();
        wrapper.children[0].classList.add('active');
        this.changeActiveClass(this.resetHover ? 0 : this.currentIndex);
      }

      wrapper.addEventListener('mouseover', (e) => {
        over(e);
      })

      wrapper.addEventListener('mouseleave', (e) => {
        leave(e);
      })
    });
  }

  // Resize slider width
  resizeSlider() {
    setTimeout(() => {
      this.slideWidth = this.slides[0]?.offsetWidth;
      this.totalWidth = this.slideWidth * this.slidesLength;
    }, 50);

    /* this.mm.add("(min-width: 1200px)", () => {
      this.animation.progress(0);
      //this.draggable.startProgress = this.animation.progress();
      this.draggable.updateProgress = this.animation.progress(0);
      this.animateSlides();
    }); */
  }
}