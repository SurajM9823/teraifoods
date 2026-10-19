(() => {
  const select = document.getElementById('id_icon');
  const preview = document.getElementById('category-icon-preview');
  const label = document.getElementById('category-icon-label');
  if (!select || !preview || !label) return;
  const update = () => {
    preview.className = select.value;
    label.textContent = select.options[select.selectedIndex].text;
  };
  select.addEventListener('change', update);
  update();
})();
