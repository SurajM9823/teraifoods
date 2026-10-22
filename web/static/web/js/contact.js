document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.faq-accordion-header').forEach(button => {
    button.addEventListener('click', () => {
      const open = button.closest('.faq-accordion-item').classList.toggle('is-open');
      button.setAttribute('aria-expanded', String(open));
    });
  });
  const form = document.getElementById('terai-contact-form');
  const feedback = document.createElement('p');
  feedback.setAttribute('role', 'alert');
  form.append(feedback);
  form.addEventListener('submit', async event => {
    event.preventDefault();
    const button = form.querySelector('[type="submit"]');
    button.disabled = true;
    feedback.textContent = '';
    document.getElementById('contact-success-alert').classList.add('d-none');
    try {
      const response = await fetch(form.action, {method: 'POST', body: new FormData(form), credentials: 'same-origin'});
      const data = await response.json();
      if (!response.ok) throw new Error(Object.values(data.errors || {}).flat().join(' ') || 'Unable to send your enquiry. Please try again.');
      document.getElementById('contact-success-alert').classList.remove('d-none');
      feedback.textContent = 'Enquiry reference: ' + data.reference;
      form.reset();
    } catch (error) {
      feedback.textContent = error.message;
    } finally { button.disabled = false; }
  });
  if (typeof L === 'undefined') return;
  const map = L.map('contact-delivery-map', {center: [53.5, -2], zoom: 6, scrollWheelZoom: false});
  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
    subdomains: 'abcd',
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions" target="_blank" rel="noopener">CARTO</a>'
  }).addTo(map);
  const hubs = JSON.parse(document.getElementById('contact-hubs-data').textContent);
  hubs.forEach(hub => {
    const label = document.createElement('div');
    label.style.cssText = 'background:#634c9f;color:#fff;padding:3px 6px;font-size:10px;font-weight:800;border:1px solid #fff;white-space:nowrap;display:inline-flex';
    label.textContent = hub.tag;
    const popup = document.createElement('div');
    popup.style.cssText = 'font-family:Inter,sans-serif;font-size:11.5px;white-space:pre-line';
    const title = document.createElement('strong');
    title.textContent = hub.name;
    popup.append(title, document.createElement('br'), document.createTextNode(hub.description));
    L.marker([hub.latitude, hub.longitude], {icon: L.divIcon({className:'terai-map-marker', html:label, iconSize:[80,24], iconAnchor:[40,12]})}).addTo(map).bindPopup(popup);
  });
  setTimeout(() => map.invalidateSize(), 300);
});
