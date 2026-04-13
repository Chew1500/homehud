"""Grocery tab: categorized shopping list with drag/drop and checkboxes."""

TAB_HTML = """\
<div class="tab-panel" id="tab-grocery">
  <style>
    #tab-grocery { padding-bottom: env(safe-area-inset-bottom); }
    #grocery-add-bar {
      display: flex; gap: 0.5rem; margin-bottom: 1rem;
      position: sticky; top: 0; background: #fff; padding: 0.5rem 0;
      z-index: 5;
    }
    #grocery-add-input {
      flex: 1; padding: 0.75rem; font-size: 1rem;
      border: 1px solid #ddd; border-radius: 8px;
    }
    #grocery-add-bar button {
      padding: 0.75rem 1rem; background: #3b82f6; color: #fff;
      border: none; border-radius: 8px; font-size: 1rem;
      font-weight: 600; cursor: pointer;
    }
    #grocery-toolbar {
      display: flex; gap: 0.5rem; margin-bottom: 0.75rem;
      flex-wrap: wrap;
    }
    #grocery-toolbar button {
      padding: 0.5rem 0.8rem; background: #f1f5f9;
      border: 1px solid #e2e8f0; border-radius: 6px;
      font-size: 0.85rem; cursor: pointer; color: #334155;
    }
    #grocery-toolbar button.active {
      background: #3b82f6; color: #fff; border-color: #3b82f6;
    }
    .grocery-section { margin-bottom: 1rem; }
    .grocery-section-header {
      display: flex; align-items: center; justify-content: space-between;
      padding: 0.6rem 0.75rem; background: #f8fafc;
      border-left: 4px solid #3b82f6; border-radius: 6px;
      font-weight: 600; color: #0f172a; font-size: 0.95rem;
      text-transform: uppercase; letter-spacing: 0.03em;
      user-select: none;
    }
    .grocery-section-header .count {
      font-weight: 400; color: #64748b; font-size: 0.8rem;
    }
    .grocery-section.drag-over .grocery-section-header,
    .grocery-section.drag-over ul {
      background: #dbeafe;
    }
    .grocery-section ul {
      list-style: none; padding: 0.25rem 0 0 0; margin: 0;
    }
    .grocery-item {
      display: flex; align-items: center; gap: 0.75rem;
      padding: 0.85rem 0.75rem; border-bottom: 1px solid #f1f5f9;
      background: #fff; touch-action: pan-y;
    }
    .grocery-item.checked .grocery-item-name {
      text-decoration: line-through; color: #94a3b8;
    }
    .grocery-item.dragging { opacity: 0.4; }
    .grocery-item.drop-above { border-top: 2px solid #3b82f6; }
    .grocery-item.drop-below { border-bottom: 2px solid #3b82f6; }
    .grocery-item input[type=checkbox] {
      width: 24px; height: 24px; flex-shrink: 0; cursor: pointer;
    }
    .grocery-item-name { flex: 1; font-size: 1rem; color: #0f172a; }
    .grocery-item-handle {
      color: #cbd5e1; font-size: 1.4rem; cursor: grab;
      padding: 0 0.25rem; user-select: none;
    }
    .grocery-item-delete {
      background: none; border: none; color: #cbd5e1;
      font-size: 1.2rem; cursor: pointer; padding: 0.25rem 0.5rem;
    }
    .grocery-item-delete:hover { color: #ef4444; }
    #grocery-empty {
      text-align: center; color: #94a3b8; padding: 2rem 1rem;
    }
    .grocery-cat-order-item {
      padding: 0.75rem 1rem; background: #fff;
      border: 1px solid #e2e8f0; border-radius: 6px;
      margin-bottom: 0.4rem; cursor: grab; font-weight: 600;
      display: flex; align-items: center; gap: 0.75rem;
    }
    .grocery-cat-order-item.dragging { opacity: 0.4; }
    .grocery-cat-order-item.drop-above { border-top: 2px solid #3b82f6; }
    .grocery-cat-order-item.drop-below { border-bottom: 2px solid #3b82f6; }
  </style>

  <div id="grocery-loading" class="loading">Loading grocery list...</div>
  <div id="grocery-error" class="error-msg" style="display:none"></div>

  <div id="grocery-main" style="display:none">
    <div id="grocery-add-bar">
      <input id="grocery-add-input" type="text"
        placeholder="Add an item..."
        onkeydown="if(event.key==='Enter')groceryAdd()">
      <button onclick="groceryAdd()">Add</button>
    </div>

    <div id="grocery-toolbar">
      <button id="grocery-clear-btn" onclick="groceryClearChecked()">
        Clear purchased
      </button>
      <button id="grocery-edit-order-btn" onclick="groceryToggleOrderMode()">
        Edit category order
      </button>
    </div>

    <div id="grocery-sections"></div>
    <div id="grocery-cat-order-view" style="display:none">
      <p style="color:#64748b;font-size:0.9rem;margin-bottom:0.75rem">
        Drag categories into the order you walk the store.
      </p>
      <div id="grocery-cat-order-list"></div>
      <button onclick="groceryToggleOrderMode()"
        style="margin-top:1rem;padding:0.6rem 1.2rem;background:#3b82f6;
        color:#fff;border:none;border-radius:6px;font-weight:600;
        cursor:pointer">Done</button>
    </div>
    <div id="grocery-empty" style="display:none">
      <p style="font-size:1.1rem">Your grocery list is empty</p>
      <p style="margin-top:0.5rem;font-size:0.9rem">
        Add items above or say "add milk to the grocery list"
      </p>
    </div>
  </div>
</div>
"""

TAB_JS = """\
// --- Grocery tab ---
let groceryState = { items: [], category_order: [], categories: [] };
let groceryOrderMode = false;
let groceryDragId = null;
let groceryDragCategory = null;

async function loadGrocery() {
  try {
    const data = await fetchJSON('/api/grocery');
    groceryState = data;
    renderGrocery();
    document.getElementById('grocery-loading').style.display = 'none';
    document.getElementById('grocery-main').style.display = '';
  } catch (e) {
    const err = document.getElementById('grocery-error');
    err.textContent = 'Failed to load grocery list: ' + e.message;
    err.style.display = '';
    document.getElementById('grocery-loading').style.display = 'none';
  }
}

function renderGrocery() {
  const container = document.getElementById('grocery-sections');
  const empty = document.getElementById('grocery-empty');
  if (!groceryState.items.length) {
    container.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';

  const byCat = {};
  for (const it of groceryState.items) {
    const c = it.category || 'Uncategorized';
    (byCat[c] = byCat[c] || []).push(it);
  }

  const order = groceryState.category_order.slice();
  for (const c of Object.keys(byCat)) {
    if (!order.includes(c)) order.push(c);
  }

  let html = '';
  for (const cat of order) {
    const items = byCat[cat];
    if (!items || !items.length) continue;
    html += '<div class="grocery-section" data-category="'
      + escapeHtml(cat) + '" ondragover="groceryDragOverSection(event)"'
      + ' ondragleave="groceryDragLeaveSection(event)"'
      + ' ondrop="groceryDropOnSection(event)">';
    html += '<div class="grocery-section-header">'
      + '<span>' + escapeHtml(cat) + '</span>'
      + '<span class="count">' + items.length + '</span></div>';
    html += '<ul>';
    for (const it of items) {
      const checked = it.checked ? 'checked' : '';
      const cls = it.checked ? 'grocery-item checked' : 'grocery-item';
      html += '<li class="' + cls + '" draggable="true"'
        + ' data-id="' + it.id + '"'
        + ' data-category="' + escapeHtml(cat) + '"'
        + ' ondragstart="groceryDragStart(event)"'
        + ' ondragend="groceryDragEnd(event)"'
        + ' ondragover="groceryDragOverItem(event)"'
        + ' ondragleave="groceryDragLeaveItem(event)"'
        + ' ondrop="groceryDropOnItem(event)">'
        + '<input type="checkbox" ' + checked
        + ' onchange="groceryToggleChecked(\\'' + it.id + '\\', this.checked)">'
        + '<span class="grocery-item-name">' + escapeHtml(it.name) + '</span>'
        + '<button class="grocery-item-delete" title="Remove"'
        + ' onclick="groceryDelete(\\'' + it.id + '\\')">&times;</button>'
        + '<span class="grocery-item-handle">&#8942;&#8942;</span>'
        + '</li>';
    }
    html += '</ul></div>';
  }
  container.innerHTML = html;
}

async function groceryAdd() {
  const input = document.getElementById('grocery-add-input');
  const name = input.value.trim();
  if (!name) return;
  input.value = '';
  try {
    const res = await fetch('/api/grocery', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name}),
    });
    if (!res.ok && res.status !== 409) {
      throw new Error('HTTP ' + res.status);
    }
    // Reload from server so the LLM can categorize any uncategorized items
    await loadGrocery();
  } catch (e) {
    alert('Failed to add item: ' + e.message);
  }
}

async function groceryToggleChecked(id, checked) {
  // Optimistic update
  const item = groceryState.items.find(i => i.id === id);
  if (item) item.checked = checked;
  renderGrocery();
  try {
    await fetch('/api/grocery/' + id, {
      method: 'PATCH',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({checked}),
    });
  } catch (e) {
    console.warn('Check toggle failed', e);
  }
}

async function groceryDelete(id) {
  groceryState.items = groceryState.items.filter(i => i.id !== id);
  renderGrocery();
  try {
    await fetch('/api/grocery/' + id, {method: 'DELETE'});
  } catch (e) {
    console.warn('Delete failed', e);
  }
}

async function groceryClearChecked() {
  if (!confirm('Remove all purchased items?')) return;
  try {
    await fetch('/api/grocery/clear-checked', {method: 'POST'});
    await loadGrocery();
  } catch (e) {
    alert('Failed: ' + e.message);
  }
}

// --- Item drag & drop ---

function groceryDragStart(e) {
  const li = e.currentTarget;
  groceryDragId = li.dataset.id;
  groceryDragCategory = li.dataset.category;
  li.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
  try { e.dataTransfer.setData('text/plain', groceryDragId); } catch (_) {}
}

function groceryDragEnd(e) {
  e.currentTarget.classList.remove('dragging');
  document.querySelectorAll('.grocery-item.drop-above, .grocery-item.drop-below')
    .forEach(el => el.classList.remove('drop-above', 'drop-below'));
  document.querySelectorAll('.grocery-section.drag-over')
    .forEach(el => el.classList.remove('drag-over'));
  groceryDragId = null;
  groceryDragCategory = null;
}

function groceryDragOverItem(e) {
  if (!groceryDragId) return;
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  const li = e.currentTarget;
  if (li.dataset.id === groceryDragId) return;
  const rect = li.getBoundingClientRect();
  const above = (e.clientY - rect.top) < rect.height / 2;
  li.classList.toggle('drop-above', above);
  li.classList.toggle('drop-below', !above);
}

function groceryDragLeaveItem(e) {
  e.currentTarget.classList.remove('drop-above', 'drop-below');
}

function groceryDragOverSection(e) {
  if (!groceryDragId) return;
  e.preventDefault();
  e.currentTarget.classList.add('drag-over');
}

function groceryDragLeaveSection(e) {
  if (!e.currentTarget.contains(e.relatedTarget)) {
    e.currentTarget.classList.remove('drag-over');
  }
}

async function groceryDropOnItem(e) {
  if (!groceryDragId) return;
  e.preventDefault();
  e.stopPropagation();
  const li = e.currentTarget;
  const targetId = li.dataset.id;
  const targetCategory = li.dataset.category;
  const rect = li.getBoundingClientRect();
  const above = (e.clientY - rect.top) < rect.height / 2;
  li.classList.remove('drop-above', 'drop-below');

  await groceryMoveItem(groceryDragId, targetCategory, targetId, above);
}

async function groceryDropOnSection(e) {
  if (!groceryDragId) return;
  e.preventDefault();
  const section = e.currentTarget;
  section.classList.remove('drag-over');
  // Only trigger if dropped on blank section space (not inside a li)
  if (e.target.closest('.grocery-item')) return;
  const targetCategory = section.dataset.category;
  await groceryMoveItem(groceryDragId, targetCategory, null, false);
}

async function groceryMoveItem(itemId, newCategory, anchorId, above) {
  const item = groceryState.items.find(i => i.id === itemId);
  if (!item) return;

  // Update category if changed (server-side PATCH)
  if (item.category !== newCategory) {
    item.category = newCategory;
    try {
      await fetch('/api/grocery/' + itemId, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({category: newCategory}),
      });
    } catch (e) {
      console.warn('Category update failed', e);
    }
  }

  // Rebuild order: remove the dragged item, insert it at the anchor position
  const without = groceryState.items.filter(i => i.id !== itemId);
  let insertAt = without.length;
  if (anchorId) {
    const anchorIdx = without.findIndex(i => i.id === anchorId);
    if (anchorIdx >= 0) insertAt = above ? anchorIdx : anchorIdx + 1;
  } else {
    // Dropped on empty section space — place at the end of that category
    const lastIdx = without.reduce((acc, it, idx) =>
      it.category === newCategory ? idx : acc, -1);
    insertAt = lastIdx + 1;
    if (lastIdx < 0) insertAt = without.length;
  }
  without.splice(insertAt, 0, item);
  groceryState.items = without;
  renderGrocery();

  try {
    await fetch('/api/grocery/reorder', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ids: groceryState.items.map(i => i.id)}),
    });
  } catch (e) {
    console.warn('Reorder failed', e);
  }
}

// --- Category order edit mode ---

function groceryToggleOrderMode() {
  groceryOrderMode = !groceryOrderMode;
  document.getElementById('grocery-sections').style.display =
    groceryOrderMode ? 'none' : '';
  document.getElementById('grocery-add-bar').style.display =
    groceryOrderMode ? 'none' : '';
  document.getElementById('grocery-cat-order-view').style.display =
    groceryOrderMode ? '' : 'none';
  document.getElementById('grocery-edit-order-btn').classList.toggle(
    'active', groceryOrderMode);
  if (groceryOrderMode) renderCategoryOrder();
}

function renderCategoryOrder() {
  const list = document.getElementById('grocery-cat-order-list');
  let html = '';
  for (const cat of groceryState.category_order) {
    html += '<div class="grocery-cat-order-item" draggable="true"'
      + ' data-category="' + escapeHtml(cat) + '"'
      + ' ondragstart="groceryCatDragStart(event)"'
      + ' ondragend="groceryCatDragEnd(event)"'
      + ' ondragover="groceryCatDragOver(event)"'
      + ' ondragleave="groceryCatDragLeave(event)"'
      + ' ondrop="groceryCatDrop(event)">'
      + '<span style="color:#cbd5e1;font-size:1.3rem">&#8942;&#8942;</span>'
      + '<span>' + escapeHtml(cat) + '</span></div>';
  }
  list.innerHTML = html;
}

let groceryCatDragCat = null;

function groceryCatDragStart(e) {
  groceryCatDragCat = e.currentTarget.dataset.category;
  e.currentTarget.classList.add('dragging');
  e.dataTransfer.effectAllowed = 'move';
}

function groceryCatDragEnd(e) {
  e.currentTarget.classList.remove('dragging');
  document.querySelectorAll('.grocery-cat-order-item.drop-above, '
    + '.grocery-cat-order-item.drop-below')
    .forEach(el => el.classList.remove('drop-above', 'drop-below'));
  groceryCatDragCat = null;
}

function groceryCatDragOver(e) {
  if (!groceryCatDragCat) return;
  e.preventDefault();
  const el = e.currentTarget;
  if (el.dataset.category === groceryCatDragCat) return;
  const rect = el.getBoundingClientRect();
  const above = (e.clientY - rect.top) < rect.height / 2;
  el.classList.toggle('drop-above', above);
  el.classList.toggle('drop-below', !above);
}

function groceryCatDragLeave(e) {
  e.currentTarget.classList.remove('drop-above', 'drop-below');
}

async function groceryCatDrop(e) {
  if (!groceryCatDragCat) return;
  e.preventDefault();
  const el = e.currentTarget;
  const targetCat = el.dataset.category;
  const rect = el.getBoundingClientRect();
  const above = (e.clientY - rect.top) < rect.height / 2;
  el.classList.remove('drop-above', 'drop-below');

  const order = groceryState.category_order.filter(c => c !== groceryCatDragCat);
  const idx = order.indexOf(targetCat);
  if (idx < 0) return;
  order.splice(above ? idx : idx + 1, 0, groceryCatDragCat);
  groceryState.category_order = order;
  renderCategoryOrder();

  try {
    await fetch('/api/grocery/category-order', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({order}),
    });
  } catch (err) {
    console.warn('Category order save failed', err);
  }
}
"""
