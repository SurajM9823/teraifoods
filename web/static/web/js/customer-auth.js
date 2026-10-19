(() => {
  'use strict';
  const embedded = window.parent !== window;
  const notify = (type, extra = {}) => {
    if (embedded) window.parent.postMessage({type, ...extra}, window.location.origin);
  };
  if (embedded) {
    document.documentElement.classList.add('embedded-auth');
    document.querySelector('.auth-close')?.addEventListener('click', event => {
      event.preventDefault();
      notify('terai-auth-close');
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape') notify('terai-auth-close');
    });
    const card = document.querySelector('.auth-card');
    if (card) new ResizeObserver(() => notify('terai-auth-size', {height: card.scrollHeight + 2})).observe(card);
    // Successful authentication is confirmed by the server-protected profile view.
    if (window.location.pathname === '/manage-profile/') notify('terai-auth-complete');
    // Google authorization cannot run inside an iframe.
    document.querySelectorAll('form[action*="/google/"]').forEach(form => { form.target = '_top'; });
  }
  document.querySelectorAll('input[type="password"]').forEach(input => {
    const wrapper = document.createElement('div');
    wrapper.className = 'password-wrapper';
    input.before(wrapper);
    wrapper.append(input);
    const toggle = document.createElement('button');
    toggle.type = 'button';
    toggle.className = 'password-toggle';
    toggle.textContent = 'Show';
    toggle.setAttribute('aria-label', 'Show password');
    toggle.setAttribute('aria-pressed', 'false');
    toggle.addEventListener('click', () => {
      const reveal = input.type === 'password';
      input.type = reveal ? 'text' : 'password';
      toggle.textContent = reveal ? 'Hide' : 'Show';
      toggle.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
      toggle.setAttribute('aria-pressed', String(reveal));
    });
    wrapper.append(toggle);
  });
})();
