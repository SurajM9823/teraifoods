(() => {
  // Icon preview on category add/edit forms
  const select = document.getElementById('id_icon');
  const preview = document.getElementById('category-icon-preview');
  const label = document.getElementById('category-icon-label');
  if (select && preview && label) {
    const update = () => {
      preview.className = select.value;
      label.textContent = select.options[select.selectedIndex]?.text || '';
    };
    select.addEventListener('change', update);
    update();
  }

  // Collapsible categories on admin/categories/
  const initCollapsibleCategories = () => {
    const groups = document.querySelectorAll('.category-group');
    if (!groups.length) return;

    const toggleAllBtn = document.getElementById('btn-toggle-all-categories');

    const setGroupExpanded = (group, expand) => {
      const btn = group.querySelector('.category-expand-btn');
      if (expand) {
        group.classList.add('is-expanded');
        if (btn) {
          btn.setAttribute('aria-expanded', 'true');
          btn.setAttribute('title', 'Collapse subcategories');
        }
      } else {
        group.classList.remove('is-expanded');
        if (btn) {
          btn.setAttribute('aria-expanded', 'false');
          btn.setAttribute('title', 'Expand subcategories');
        }
      }
    };

    const updateToggleAllState = () => {
      if (!toggleAllBtn) return;
      const anyExpanded = Array.from(groups).some(g => g.classList.contains('is-expanded'));
      const textSpan = toggleAllBtn.querySelector('span');
      const icon = toggleAllBtn.querySelector('i');
      if (anyExpanded) {
        toggleAllBtn.setAttribute('data-action', 'collapse');
        toggleAllBtn.setAttribute('title', 'Collapse all categories');
        if (textSpan) textSpan.textContent = 'Collapse All';
        if (icon) icon.className = 'fa-solid fa-angles-up';
      } else {
        toggleAllBtn.setAttribute('data-action', 'expand');
        toggleAllBtn.setAttribute('title', 'Expand all categories');
        if (textSpan) textSpan.textContent = 'Expand All';
        if (icon) icon.className = 'fa-solid fa-angles-down';
      }
    };

    groups.forEach(group => {
      const expandBtn = group.querySelector('.category-expand-btn');
      const headerRow = group.querySelector('.category-row-main');

      if (expandBtn) {
        expandBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          const isExp = group.classList.contains('is-expanded');
          setGroupExpanded(group, !isExp);
          updateToggleAllState();
        });
      }

      if (headerRow) {
        headerRow.addEventListener('click', (e) => {
          // Ignore clicks on actionable items: links, buttons, inputs, selects, forms
          if (e.target.closest('a, button, input, select, form')) {
            return;
          }
          const isExp = group.classList.contains('is-expanded');
          setGroupExpanded(group, !isExp);
          updateToggleAllState();
        });
      }
    });

    if (toggleAllBtn) {
      toggleAllBtn.addEventListener('click', () => {
        const action = toggleAllBtn.getAttribute('data-action') || 'expand';
        const willExpand = action === 'expand';
        groups.forEach(g => setGroupExpanded(g, willExpand));
        updateToggleAllState();
      });
    }

    // If search query is present, auto-expand categories to show results
    const params = new URLSearchParams(window.location.search);
    if (params.get('q')) {
      groups.forEach(g => setGroupExpanded(g, true));
      updateToggleAllState();
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initCollapsibleCategories);
  } else {
    initCollapsibleCategories();
  }
})();
