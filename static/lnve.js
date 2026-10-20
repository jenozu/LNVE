/* LNVE interaction layer — progressive enhancement; core Flask forms remain native. */
(() => {
  'use strict';
  const one = (selector, root = document) => root.querySelector(selector);
  const all = (selector, root = document) => [...root.querySelectorAll(selector)];

  const navToggle = one('[data-open-nav]');
  const closeNav = () => {
    document.body.classList.remove('nav-open');
    navToggle?.setAttribute('aria-expanded', 'false');
  };
  navToggle?.addEventListener('click', () => {
    const isOpen = document.body.classList.toggle('nav-open');
    navToggle.setAttribute('aria-expanded', String(isOpen));
  });
  one('[data-close-nav]')?.addEventListener('click', closeNav);
  all('.sidebar .nav-link').forEach(link => link.addEventListener('click', closeNav));
  all('[data-dismiss-flash]').forEach(button => button.addEventListener('click', () => button.closest('.flash')?.remove()));
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      closeNav();
      const active = one('.audit-disclosure[open]');
      if (active) active.open = false;
    }
    const t = event.target;
    const editing = t instanceof HTMLElement && (t.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT'].includes(t.tagName));
    if (((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') || (event.key === '/' && !editing)) {
      const target = one('[data-active-pool-filter]') || one('#custom-type');
      if (target) {
        event.preventDefault();
        target.focus();
      }
    }
  });

  all('[data-range-pair]').forEach(pair => {
    const range = one('[data-range-control]', pair);
    const number = one('[data-range-number]', pair);
    if (!range || !number) return;
    range.addEventListener('input', () => { number.value = range.value; });
    number.addEventListener('input', () => {
      if (number.value !== '') range.value = number.value;
    });
    number.addEventListener('change', () => {
      const value = Number(number.value);
      if (!Number.isFinite(value)) return;
      number.value = String(Math.min(Number(number.max), Math.max(Number(number.min), value)));
      range.value = number.value;
    });
  });

  const discoveryForm = one('#prospect-search-form');
  discoveryForm?.addEventListener('submit', event => {
    const niche = one('[name="search_type"]', discoveryForm);
    const custom = one('[name="custom_type"]', discoveryForm);
    if (!niche?.value && !custom?.value.trim()) {
      event.preventDefault();
      niche?.setCustomValidity('Select a category or enter a custom business keyword.');
      niche?.reportValidity();
      return;
    }
    niche?.setCustomValidity('');
    const button = one('#start-search');
    if (button) {
      button.disabled = true;
      button.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin" aria-hidden="true"></i> Starting search…';
    }
  });
  one('#search-type')?.addEventListener('change', event => event.target.setCustomValidity(''));
  one('#custom-type')?.addEventListener('input', () => one('#search-type')?.setCustomValidity(''));

  function filterTable(table, query) {
    if (!table) return;
    let count = 0;
    const rows = all('tbody tr:not(.static-empty)', table);
    for (const row of rows) {
      const matches = row.textContent.toLowerCase().includes(query.trim().toLowerCase());
      row.hidden = !matches;
      if (matches) count += 1;
    }
    const notice = document.querySelector('[data-no-rows-for="' + table.id + '"]');
    if (notice) notice.hidden = count > 0 || rows.length === 0 || !query.trim();
  }
  all('[data-table-filter]').forEach(field => {
    field.addEventListener('input', () => filterTable(document.getElementById(field.dataset.tableFilter), field.value));
  });

  const poolFilter = one('[data-active-pool-filter]');
  function currentPanel() {
    return one('[data-tab-panel]:not([hidden])');
  }
  function activateTab(id, updateHash = false) {
    const panel = document.getElementById(id);
    if (!panel || !panel.hasAttribute('data-tab-panel')) return;
    all('[data-tab-panel]').forEach(item => { item.hidden = item.id !== id; });
    all('[data-tab]').forEach(tab => {
      const selected = tab.dataset.tab === id;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    if (poolFilter) {
      poolFilter.value = '';
      all('[data-tab-panel] table').forEach(table => filterTable(table, ''));
    }
    if (updateHash) history.replaceState(null, '', '#' + id);
  }
  all('[data-tab]').forEach(tab => {
    tab.addEventListener('click', () => activateTab(tab.dataset.tab, true));
    tab.addEventListener('keydown', event => {
      if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
      const tabs = all('[data-tab]');
      const current = tabs.indexOf(tab);
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? tabs.length - 1 :
        (current + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length;
      event.preventDefault();
      tabs[next].focus();
      activateTab(tabs[next].dataset.tab, true);
    });
  });
  if (one('[data-tab]')) {
    const hash = decodeURIComponent(location.hash.slice(1));
    if (hash === 'audit-queue' || hash === 'no-website') activateTab(hash);
  }
  window.addEventListener('hashchange', () => {
    const hash = decodeURIComponent(location.hash.slice(1));
    if (hash === 'audit-queue' || hash === 'no-website') activateTab(hash);
  });
  poolFilter?.addEventListener('input', () => filterTable(one('table', currentPanel()), poolFilter.value));

  all('[data-sort-table]').forEach(button => button.addEventListener('click', () => {
    const table = document.getElementById(button.dataset.sortTable);
    if (!table) return;
    const tbody = one('tbody', table);
    const rows = all('tr:not(.static-empty)', tbody);
    const col = Number(button.dataset.sortCol);
    const ascending = button.dataset.direction !== 'asc';
    button.dataset.direction = ascending ? 'asc' : 'desc';
    button.setAttribute('aria-pressed', 'true');
    rows.sort((a, b) => {
      const va = a.cells[col]?.dataset.sortValue ?? a.cells[col]?.textContent.trim() ?? '';
      const vb = b.cells[col]?.dataset.sortValue ?? b.cells[col]?.textContent.trim() ?? '';
      const comparison = button.dataset.sortType === 'number'
        ? Number(va) - Number(vb) : va.localeCompare(vb, undefined, { numeric: true });
      return ascending ? comparison : -comparison;
    });
    rows.forEach(row => tbody.appendChild(row));
  }));

  all('.audit-disclosure').forEach(details => {
    details.addEventListener('toggle', () => {
      if (!details.open) return;
      all('.audit-disclosure').forEach(other => { if (other !== details) other.open = false; });
    });
  });

  const runningRows = all('[data-search-id][data-search-status="running"]');
  const detailBanner = one('[data-search-detail-poll]');
  const searchTasks = runningRows.map(row => ({
    id: row.dataset.searchId, row, last: 'running'
  }));
  if (detailBanner) searchTasks.push({ id: detailBanner.dataset.searchDetailPoll, detail: true, last: 'running' });

  if (searchTasks.length) {
    const poll = async () => {
      const active = searchTasks.filter(task => task.last === 'running');
      if (!active.length || document.hidden) return;
      for (const task of active) {
        try {
          const response = await fetch('/api/search-status/' + encodeURIComponent(task.id), {
            headers: { 'Accept': 'application/json' }, credentials: 'same-origin', cache: 'no-store'
          });
          if (!response.ok) continue;
          const data = await response.json();
          if (task.row) {
            const pill = one('[data-search-status-label]', task.row);
            const count = one('[data-search-count]', task.row);
            if (count) count.textContent = String(data.total_leads ?? 0);
            if (pill) {
              pill.textContent = (data.status || 'pending').replace(/^./, c => c.toUpperCase());
              pill.className = 'pill status-' + (data.status || 'pending');
            }
          }
          if (task.detail) {
            const total = one('[data-detail-total]');
            if (total) total.textContent = String(data.total_leads ?? 0);
            if (data.status !== 'running') { location.reload(); return; }
          }
          task.last = data.status;
        } catch (_) {
          // A failed status check must not interfere with manual prospect work.
        }
      }
    };
    const timer = setInterval(() => { if (!document.hidden) poll(); }, 7000);
    window.addEventListener('pagehide', () => clearInterval(timer), { once: true });
    poll();
  }
})();
