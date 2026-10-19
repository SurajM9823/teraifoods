/**
 * Terai Food - UK Address Lookup & Instant Map Confirmation
 * Powered by Leaflet & Postcodes.io (Free UK Open Data)
 */
(function (window, document) {
  'use strict';

  // Default Central London coordinates
  const DEFAULT_LAT = 51.5074;
  const DEFAULT_LNG = -0.1278;

  // Custom SVG Map Pin
  function createPinIcon() {
    return L.divIcon({
      className: 'teraifood-map-pin-wrapper',
      html: `
        <div class="teraifood-map-pin" title="Drag me to your exact door!">
          <svg width="32" height="40" viewBox="0 0 32 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M16 0C7.163 0 0 7.163 0 16C0 28 16 40 16 40C16 40 32 28 32 16C32 7.163 24.837 0 16 0Z" fill="#1547A8"/>
            <circle cx="16" cy="15" r="6" fill="#FFFFFF"/>
            <circle cx="16" cy="15" r="3" fill="#1547A8"/>
          </svg>
          <div class="teraifood-pin-pulse"></div>
        </div>
      `,
      iconSize: [32, 40],
      iconAnchor: [16, 40],
      popupAnchor: [0, -38]
    });
  }

  // Validate standard UK postcode format
  function isUkPostcode(str) {
    if (!str) return false;
    const clean = str.replace(/\s+/g, '').toUpperCase();
    const ukRegex = /^[A-Z]{1,2}[0-9][A-Z0-9]?[0-9][A-Z]{2}$/;
    return ukRegex.test(clean);
  }

  // Format postcode nicely with standard space e.g. "SW1A 1AA"
  function formatPostcode(str) {
    if (!str) return '';
    const clean = str.replace(/\s+/g, '').toUpperCase();
    if (clean.length > 3) {
      return clean.slice(0, clean.length - 3) + ' ' + clean.slice(clean.length - 3);
    }
    return clean;
  }

  // Storage helpers
  function getSavedAddress() {
    try {
      const data = localStorage.getItem('teraifood_uk_address');
      return data ? JSON.parse(data) : null;
    } catch (e) {
      return null;
    }
  }

  function saveAddress(data) {
    try {
      localStorage.setItem('teraifood_uk_address', JSON.stringify(data));
    } catch (e) {}
  }

  // Update header "Deliver to" label
  function updateHeaderDeliverTo(label) {
    const el = document.querySelector('.location-selector-button p');
    if (el) {
      el.textContent = label || 'all';
    }
  }

  // Main initializer for a map instance
  function initUkMapInstance(config) {
    const {
      containerId,
      postcodeInputId,
      houseInputId,
      cityInputId,
      statusId,
      badgeId,
      onConfirm
    } = config;

    const mapContainer = document.getElementById(containerId);
    if (!mapContainer || typeof L === 'undefined') return null;

    const postcodeInput = document.getElementById(postcodeInputId);
    const houseInput = document.getElementById(houseInputId);
    const cityInput = cityInputId ? document.getElementById(cityInputId) : null;
    const statusEl = statusId ? document.getElementById(statusId) : null;
    const badgeEl = badgeId ? document.getElementById(badgeId) : null;

    let saved = getSavedAddress();
    let currentLat = saved && saved.lat ? saved.lat : DEFAULT_LAT;
    let currentLng = saved && saved.lng ? saved.lng : DEFAULT_LNG;
    let currentZoom = saved && saved.lat ? 17 : 13;

    // Initialize Leaflet Map
    const map = L.map(containerId, {
      center: [currentLat, currentLng],
      zoom: currentZoom,
      zoomControl: true,
      scrollWheelZoom: true
    });

    // Add OpenStreetMap tiles
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; <a href="https://openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(map);

    // Add Draggable Marker
    const marker = L.marker([currentLat, currentLng], {
      draggable: true,
      icon: createPinIcon()
    }).addTo(map);

    marker.bindPopup('<strong>Terai Food Delivery Pin</strong><br>Drag directly to your door!');

    function setStatus(text, type) {
      if (!statusEl) return;
      statusEl.textContent = text;
      statusEl.className = 'lookup-status ' + (type || '');
    }

    function setBadge(text) {
      if (!badgeEl) return;
      badgeEl.innerHTML = '<i class="klb-icon-map-pin"></i> <span>' + text + '</span>';
    }

    // Function to handle location update from postcode lookup
    async function lookupPostcode(postcodeQuery, isManual = false) {
      const clean = postcodeQuery.trim().toUpperCase();
      if (!clean) return;

      setStatus('Searching postcode...', 'loading');

      try {
        const res = await fetch(`https://api.postcodes.io/postcodes/${encodeURIComponent(clean.replace(/\s+/g, ''))}`);
        if (!res.ok) {
          if (isManual) {
            setStatus('Postcode not found in UK database. Please check.', 'error');
          }
          return;
        }

        const json = await res.json();
        if (json.status === 200 && json.result) {
          const result = json.result;
          const lat = result.latitude;
          const lng = result.longitude;
          const formatted = result.postcode;
          const district = result.admin_district || result.region || 'UK';

          if (postcodeInput && postcodeInput.value.replace(/\s+/g, '').toUpperCase() === clean.replace(/\s+/g, '')) {
            postcodeInput.value = formatted;
          }

          if (cityInput && !cityInput.value) {
            cityInput.value = district;
          }

          // Center map and move pin
          map.flyTo([lat, lng], 17, { duration: 1 });
          marker.setLatLng([lat, lng]);
          marker.openPopup();

          setStatus(`✓ Centered on ${formatted} (${district}). Drag pin to your exact door.`, 'success');
          setBadge(`Centered on ${formatted}. Drag pin right to your door.`);
        }
      } catch (err) {
        if (isManual) {
          setStatus('Lookup temporarily unavailable offline. You can position the pin directly.', 'error');
        }
      }
    }

    // Reverse lookup lat/lng to postcode and district
    async function reverseLookup(lat, lng) {
      try {
        const res = await fetch(`https://api.postcodes.io/postcodes?lat=${lat}&lon=${lng}`);
        if (res.ok) {
          const json = await res.json();
          if (json.status === 200 && json.result && json.result.length > 0) {
            const nearest = json.result[0];
            if (postcodeInput && (!postcodeInput.value || postcodeInput.value === 'Current Location')) {
              postcodeInput.value = nearest.postcode;
            }
            if (cityInput && !cityInput.value) {
              cityInput.value = nearest.admin_district || nearest.region;
            }
            setBadge(`Door pin: ${nearest.postcode} (${lat.toFixed(5)}, ${lng.toFixed(5)})`);
            setStatus(`✓ Precise door pin selected near ${nearest.postcode}`, 'success');
            return;
          }
        }
      } catch (e) {}
      setBadge(`Door pin placed at ${lat.toFixed(5)}, ${lng.toFixed(5)}`);
      setStatus(`✓ Door pin placed! Drag to adjust anytime.`, 'success');
    }

    // Draggable marker event
    marker.on('dragend', function () {
      const pos = marker.getLatLng();
      reverseLookup(pos.lat, pos.lng);
    });

    // Map click moves marker
    map.on('click', function (e) {
      marker.setLatLng(e.latlng);
      reverseLookup(e.latlng.lat, e.latlng.lng);
    });

    // Postcode typing listener with debounce
    let debounceTimer;
    if (postcodeInput) {
      postcodeInput.addEventListener('input', function (e) {
        clearTimeout(debounceTimer);
        const val = e.target.value.trim();
        if (isUkPostcode(val)) {
          debounceTimer = setTimeout(() => {
            lookupPostcode(val, false);
          }, 350);
        } else if (val.length >= 5) {
          debounceTimer = setTimeout(() => {
            lookupPostcode(val, false);
          }, 600);
        }
      });

      postcodeInput.addEventListener('blur', function (e) {
        const val = e.target.value.trim();
        if (val) {
          lookupPostcode(val, true);
        }
      });

      postcodeInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          e.preventDefault();
          lookupPostcode(e.target.value.trim(), true);
        }
      });
    }

    // Geolocation helper
    function locateCurrentPosition() {
      if (!navigator.geolocation) {
        setStatus('Geolocation is not supported by your browser.', 'error');
        return;
      }
      setStatus('Locating your current GPS position...', 'loading');
      navigator.geolocation.getCurrentPosition(
        async function (position) {
          const lat = position.coords.latitude;
          const lng = position.coords.longitude;
          map.flyTo([lat, lng], 17, { duration: 1.2 });
          marker.setLatLng([lat, lng]);
          await reverseLookup(lat, lng);
        },
        function (err) {
          setStatus('Could not retrieve current location. Please enter your postcode above.', 'error');
        },
        { enableHighAccuracy: true, timeout: 8000 }
      );
    }

    // If pre-existing saved address, populate
    if (saved && saved.postcode && saved.postcode !== 'all') {
      if (postcodeInput) postcodeInput.value = saved.postcode;
      if (houseInput && saved.houseNumber) houseInput.value = saved.houseNumber;
      if (cityInput && saved.city) cityInput.value = saved.city;
      if (saved.lat && saved.lng) {
        marker.setLatLng([saved.lat, saved.lng]);
        setBadge(`Saved Address: ${saved.houseNumber ? saved.houseNumber + ', ' : ''}${saved.postcode}`);
      }
    }

    return {
      map,
      marker,
      lookupPostcode,
      locateCurrentPosition,
      getDetails: () => {
        const pos = marker.getLatLng();
        return {
          postcode: postcodeInput ? postcodeInput.value.trim().toUpperCase() : '',
          houseNumber: houseInput ? houseInput.value.trim() : '',
          city: cityInput ? cityInput.value.trim() : '',
          lat: pos.lat,
          lng: pos.lng
        };
      }
    };
  }

  // Initialize Modal Delivery Selector on index.html
  function setupHeaderModalDelivery() {
    const modalEl = document.getElementById('location-selector');
    if (!modalEl) return;

    let mapInstance = null;

    // Check if user already had a saved location
    const saved = getSavedAddress();
    if (saved && saved.isAll) {
      updateHeaderDeliverTo('all');
    } else if (saved && saved.isCurrentLocation) {
      updateHeaderDeliverTo('Current Location');
    } else if (saved && saved.postcode) {
      updateHeaderDeliverTo(saved.postcode);
    } else {
      updateHeaderDeliverTo('all');
    }

    // Modal open observer to invalidate Leaflet map size
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'class') {
          if (modalEl.classList.contains('active')) {
            if (!mapInstance) {
              mapInstance = initUkMapInstance({
                containerId: 'modal-delivery-map',
                postcodeInputId: 'modal-postcode-input',
                houseInputId: 'modal-house-input',
                statusId: 'modal-lookup-status',
                badgeId: 'modal-map-badge'
              });
            }
            if (mapInstance && mapInstance.map) {
              setTimeout(() => {
                mapInstance.map.invalidateSize();
              }, 200);
            }
          }
        }
      });
    });

    observer.observe(modalEl, { attributes: true });

    // "Use Current Location" button in modal
    const geoBtn = document.getElementById('btn-modal-geolocate');
    if (geoBtn) {
      geoBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (mapInstance) {
          mapInstance.locateCurrentPosition();
        }
      });
    }

    // "Deliver to: All UK" button in modal (mark auto as all)
    const allBtn = document.getElementById('btn-modal-deliver-all');
    if (allBtn) {
      allBtn.addEventListener('click', (e) => {
        e.preventDefault();
        saveAddress({ isAll: true, label: 'all' });
        updateHeaderDeliverTo('all');
        const postcodeInput = document.getElementById('modal-postcode-input');
        const houseInput = document.getElementById('modal-house-input');
        if (postcodeInput) postcodeInput.value = '';
        if (houseInput) houseInput.value = '';
        const statusEl = document.getElementById('modal-lookup-status');
        if (statusEl) {
          statusEl.textContent = '✓ Set to Deliver to All UK.';
          statusEl.className = 'lookup-status success';
        }
        setTimeout(() => {
          modalEl.classList.remove('active');
        }, 300);
      });
    }

    // Search button in modal input
    const searchBtn = document.getElementById('btn-modal-search-postcode');
    if (searchBtn) {
      searchBtn.addEventListener('click', (e) => {
        e.preventDefault();
        const postcodeInput = document.getElementById('modal-postcode-input');
        if (postcodeInput && mapInstance) {
          mapInstance.lookupPostcode(postcodeInput.value.trim(), true);
        }
      });
    }

    // "Confirm Delivery Address" button in modal
    const confirmBtn = document.getElementById('btn-modal-confirm-address');
    if (confirmBtn) {
      confirmBtn.addEventListener('click', (e) => {
        e.preventDefault();
        if (!mapInstance) return;
        const details = mapInstance.getDetails();

        if (!details.postcode) {
          const statusEl = document.getElementById('modal-lookup-status');
          if (statusEl) {
            statusEl.textContent = 'Please enter a valid UK postcode or select All UK.';
            statusEl.className = 'lookup-status error';
          }
          return;
        }

        saveAddress({
          ...details,
          isAll: false,
          label: details.houseNumber ? `${details.houseNumber}, ${details.postcode}` : details.postcode
        });

        updateHeaderDeliverTo(details.postcode);
        modalEl.classList.remove('active');
      });
    }
  }

  // Expose API
  window.TeraiFoodMap = {
    initUkMapInstance,
    getSavedAddress,
    saveAddress,
    updateHeaderDeliverTo,
    isUkPostcode,
    formatPostcode
  };

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupHeaderModalDelivery);
  } else {
    setupHeaderModalDelivery();
  }

})(window, document);

