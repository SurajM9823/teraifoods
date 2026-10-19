(() => {
  const tabs = document.querySelectorAll('[data-account-tab]');
  function activate(name) {
    if (!['profile', 'address', 'payment'].includes(name)) name = 'profile';
    document.querySelectorAll('.account-tab-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === `pane-${name}`);
    });
    tabs.forEach(tab => tab.classList.toggle('active', tab.dataset.accountTab === name));
    const crumb = document.getElementById('crumb-active-tab');
    if (crumb) crumb.textContent = {profile: 'Manage My Account', address: 'Address Book', payment: 'My Payment Options'}[name];
  }
  tabs.forEach(tab => tab.addEventListener('click', () => activate(tab.dataset.accountTab)));
  window.addEventListener('hashchange', () => activate(location.hash.slice(1)));
  activate(location.hash.slice(1));
})();
