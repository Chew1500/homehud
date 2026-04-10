"""Recipes tab: browse, upload, edit, and manage recipes."""

TAB_HTML = """\
<div class="tab-panel" id="tab-recipes">
  <div id="recipes-loading" class="loading">Loading recipes...</div>
  <div id="recipes-error" class="error-msg" style="display:none"></div>

  <!-- List view -->
  <div id="recipes-list-view" style="display:none">
    <div style="display:flex;gap:0.5rem;margin-bottom:1rem;align-items:center">
      <input id="recipes-search" type="text" placeholder="Search recipes..."
        style="flex:1;padding:0.6rem;border:1px solid #ddd;border-radius:6px;
        font-size:1rem" oninput="filterRecipes()">
      <button onclick="showRecipeUpload()"
        style="padding:0.6rem 1rem;background:#3b82f6;color:#fff;border:none;
        border-radius:6px;font-size:1rem;cursor:pointer;white-space:nowrap;
        font-weight:600">+ Upload</button>
    </div>
    <div id="recipes-cards"></div>
    <div id="recipes-empty" style="display:none;text-align:center;
      color:#888;padding:2rem">
      <p style="font-size:1.1rem">No recipes yet</p>
      <p style="margin-top:0.5rem">Tap <strong>+ Upload</strong> to add a
      recipe from a photo</p>
    </div>
  </div>

  <!-- Detail view -->
  <div id="recipes-detail-view" style="display:none">
    <button onclick="showRecipesList()"
      style="background:none;border:none;color:#3b82f6;font-size:1rem;
      cursor:pointer;padding:0;margin-bottom:1rem">&larr; Back to recipes</button>
    <div id="recipe-detail-content"></div>
  </div>

  <!-- Upload view -->
  <div id="recipes-upload-view" style="display:none">
    <button onclick="showRecipesList()"
      style="background:none;border:none;color:#3b82f6;font-size:1rem;
      cursor:pointer;padding:0;margin-bottom:1rem">&larr; Back to recipes</button>
    <h2 style="margin-bottom:1rem">Upload Recipe Photo</h2>
    <div style="text-align:center;padding:2rem">
      <label for="recipe-file-input"
        style="display:inline-block;padding:1.5rem 2rem;background:#f0f4ff;
        border:2px dashed #3b82f6;border-radius:12px;cursor:pointer;
        font-size:1.1rem;color:#3b82f6">
        Tap to select a photo
      </label>
      <input id="recipe-file-input" type="file" accept="image/*"
        capture="environment" style="display:none"
        onchange="handleRecipeFileSelect(event)">
      <div id="recipe-upload-preview" style="margin-top:1rem"></div>
      <div id="recipe-upload-spinner" style="display:none;margin-top:1rem">
        <div class="loading">Parsing recipe from image... this may take a moment</div>
      </div>
    </div>
  </div>

  <!-- Edit/review view (after upload or manual edit) -->
  <div id="recipes-edit-view" style="display:none">
    <button onclick="showRecipesList()"
      style="background:none;border:none;color:#3b82f6;font-size:1rem;
      cursor:pointer;padding:0;margin-bottom:1rem">&larr; Back to recipes</button>
    <h2 id="recipe-edit-title" style="margin-bottom:1rem">Review Recipe</h2>
    <div style="display:flex;flex-direction:column;gap:0.75rem">
      <label>
        <span style="font-weight:600;font-size:0.9rem">Name</span>
        <input id="recipe-edit-name" type="text"
          style="width:100%;padding:0.5rem;border:1px solid #ddd;
          border-radius:6px;font-size:1rem;margin-top:0.25rem;
          box-sizing:border-box">
      </label>
      <label>
        <span style="font-weight:600;font-size:0.9rem">Tags
          <span style="font-weight:normal;color:#888">(comma separated)</span></span>
        <input id="recipe-edit-tags" type="text"
          style="width:100%;padding:0.5rem;border:1px solid #ddd;
          border-radius:6px;font-size:1rem;margin-top:0.25rem;
          box-sizing:border-box">
      </label>
      <div style="display:flex;gap:0.5rem">
        <label style="flex:1">
          <span style="font-weight:600;font-size:0.9rem">Prep (min)</span>
          <input id="recipe-edit-prep" type="number" min="0"
            style="width:100%;padding:0.5rem;border:1px solid #ddd;
            border-radius:6px;font-size:1rem;margin-top:0.25rem;
            box-sizing:border-box">
        </label>
        <label style="flex:1">
          <span style="font-weight:600;font-size:0.9rem">Cook (min)</span>
          <input id="recipe-edit-cook" type="number" min="0"
            style="width:100%;padding:0.5rem;border:1px solid #ddd;
            border-radius:6px;font-size:1rem;margin-top:0.25rem;
            box-sizing:border-box">
        </label>
        <label style="flex:1">
          <span style="font-weight:600;font-size:0.9rem">Servings</span>
          <input id="recipe-edit-servings" type="number" min="1"
            style="width:100%;padding:0.5rem;border:1px solid #ddd;
            border-radius:6px;font-size:1rem;margin-top:0.25rem;
            box-sizing:border-box">
        </label>
      </div>
      <label>
        <span style="font-weight:600;font-size:0.9rem">Ingredients
          <span style="font-weight:normal;color:#888">(one per line: qty unit name)</span></span>
        <textarea id="recipe-edit-ingredients" rows="8"
          style="width:100%;padding:0.5rem;border:1px solid #ddd;
          border-radius:6px;font-size:0.95rem;font-family:inherit;
          margin-top:0.25rem;box-sizing:border-box"></textarea>
      </label>
      <label>
        <span style="font-weight:600;font-size:0.9rem">Directions
          <span style="font-weight:normal;color:#888">(one step per line)</span></span>
        <textarea id="recipe-edit-directions" rows="10"
          style="width:100%;padding:0.5rem;border:1px solid #ddd;
          border-radius:6px;font-size:0.95rem;font-family:inherit;
          margin-top:0.25rem;box-sizing:border-box"></textarea>
      </label>
      <button id="recipe-save-btn" onclick="saveRecipeEdit()"
        style="padding:0.7rem;background:#22c55e;color:#fff;border:none;
        border-radius:6px;font-size:1rem;cursor:pointer;font-weight:600;
        margin-top:0.5rem">Save Recipe</button>
    </div>
  </div>
</div>
"""

TAB_JS = """\
let allRecipes = [];
let editingRecipeId = null;
let editingRecipeData = null;

async function loadRecipes() {
  const loading = document.getElementById('recipes-loading');
  const error = document.getElementById('recipes-error');
  const listView = document.getElementById('recipes-list-view');
  try {
    allRecipes = await fetchJSON('/api/recipes');
    loading.style.display = 'none';
    error.style.display = 'none';
    listView.style.display = '';
    renderRecipeCards(allRecipes);
  } catch (e) {
    loading.style.display = 'none';
    error.style.display = '';
    error.textContent = 'Failed to load recipes: ' + e.message;
  }
}

function renderRecipeCards(recipes) {
  const container = document.getElementById('recipes-cards');
  const empty = document.getElementById('recipes-empty');
  if (!recipes.length) {
    container.innerHTML = '';
    empty.style.display = '';
    return;
  }
  empty.style.display = 'none';
  container.innerHTML = recipes.map(r => {
    const tags = (r.tags || []).map(t =>
      `<span style="display:inline-block;background:#e0e7ff;color:#3b82f6;
        padding:0.15rem 0.5rem;border-radius:10px;font-size:0.75rem;
        margin-right:0.25rem">${escapeHtml(t)}</span>`
    ).join('');
    const time = [];
    if (r.prep_time_min) time.push(r.prep_time_min + 'm prep');
    if (r.cook_time_min) time.push(r.cook_time_min + 'm cook');
    const timeStr = time.length ? time.join(', ') : '';
    const servings = r.servings ? `Serves ${r.servings}` : '';
    const meta = [timeStr, servings].filter(Boolean).join(' &middot; ');
    return `<div onclick="showRecipeDetail('${r.id}')"
      style="background:#fff;border:1px solid #e5e7eb;border-radius:10px;
      padding:1rem;margin-bottom:0.75rem;cursor:pointer;
      transition:box-shadow 0.15s"
      onmouseenter="this.style.boxShadow='0 2px 8px rgba(0,0,0,0.08)'"
      onmouseleave="this.style.boxShadow='none'">
      <div style="font-weight:600;font-size:1.05rem;margin-bottom:0.3rem">
        ${escapeHtml(r.name)}</div>
      <div style="margin-bottom:0.3rem">${tags}</div>
      ${meta ? `<div style="font-size:0.85rem;color:#888">${meta}</div>` : ''}
    </div>`;
  }).join('');
}

function filterRecipes() {
  const q = document.getElementById('recipes-search').value.toLowerCase();
  if (!q) { renderRecipeCards(allRecipes); return; }
  const filtered = allRecipes.filter(r =>
    r.name.toLowerCase().includes(q) ||
    (r.tags || []).some(t => t.toLowerCase().includes(q))
  );
  renderRecipeCards(filtered);
}

function showRecipesList() {
  ['recipes-list-view','recipes-detail-view','recipes-upload-view',
   'recipes-edit-view'].forEach(id => {
    document.getElementById(id).style.display = id === 'recipes-list-view' ? '' : 'none';
  });
  loadRecipes();
}

async function showRecipeDetail(id) {
  const recipe = allRecipes.find(r => r.id === id);
  if (!recipe) return;

  ['recipes-list-view','recipes-upload-view','recipes-edit-view'].forEach(id =>
    document.getElementById(id).style.display = 'none');
  document.getElementById('recipes-detail-view').style.display = '';

  const ingredients = (recipe.ingredients || []).map(i => {
    const parts = [i.quantity, i.unit, i.name].filter(Boolean);
    return `<li style="padding:0.3rem 0">${escapeHtml(parts.join(' '))}</li>`;
  }).join('');

  const directions = (recipe.directions || []).map((d, idx) =>
    `<li style="padding:0.4rem 0;line-height:1.5">
      <strong>Step ${idx + 1}:</strong> ${escapeHtml(d)}</li>`
  ).join('');

  const tags = (recipe.tags || []).map(t =>
    `<span style="display:inline-block;background:#e0e7ff;color:#3b82f6;
      padding:0.2rem 0.6rem;border-radius:10px;font-size:0.8rem;
      margin-right:0.3rem">${escapeHtml(t)}</span>`
  ).join('');

  const time = [];
  if (recipe.prep_time_min) time.push(recipe.prep_time_min + ' min prep');
  if (recipe.cook_time_min) time.push(recipe.cook_time_min + ' min cook');
  const servings = recipe.servings ? `Serves ${recipe.servings}` : '';
  const meta = [...time, servings].filter(Boolean).join(' &middot; ');

  document.getElementById('recipe-detail-content').innerHTML = `
    <h2 style="margin-bottom:0.5rem">${escapeHtml(recipe.name)}</h2>
    ${tags ? `<div style="margin-bottom:0.5rem">${tags}</div>` : ''}
    ${meta ? `<div style="color:#888;font-size:0.9rem;margin-bottom:1rem">${meta}</div>` : ''}

    <h3 style="margin-top:1rem;margin-bottom:0.5rem">Ingredients</h3>
    <ul style="list-style:disc;padding-left:1.2rem">${ingredients || '<li>No ingredients</li>'}</ul>

    <h3 style="margin-top:1.25rem;margin-bottom:0.5rem">Directions</h3>
    <ol style="padding-left:1.2rem">${directions || '<li>No directions</li>'}</ol>

    <div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:1.5rem">
      <button onclick="editRecipe('${recipe.id}')"
        style="padding:0.6rem 1.2rem;background:#3b82f6;color:#fff;border:none;
        border-radius:6px;font-size:0.95rem;cursor:pointer">Edit</button>
      <button onclick="deleteRecipe('${recipe.id}','${escapeHtml(recipe.name)}')"
        style="padding:0.6rem 1.2rem;background:#ef4444;color:#fff;border:none;
        border-radius:6px;font-size:0.95rem;cursor:pointer">Delete</button>
    </div>
  `;
}

function showRecipeUpload() {
  ['recipes-list-view','recipes-detail-view','recipes-edit-view'].forEach(id =>
    document.getElementById(id).style.display = 'none');
  document.getElementById('recipes-upload-view').style.display = '';
  document.getElementById('recipe-upload-preview').innerHTML = '';
  document.getElementById('recipe-upload-spinner').style.display = 'none';
  document.getElementById('recipe-file-input').value = '';
}

async function handleRecipeFileSelect(event) {
  const file = event.target.files[0];
  if (!file) return;

  // Show preview
  const preview = document.getElementById('recipe-upload-preview');
  const reader = new FileReader();
  reader.onload = async function(e) {
    preview.innerHTML = `<img src="${e.target.result}"
      style="max-width:100%;max-height:300px;border-radius:8px;margin-top:0.5rem">`;

    // Send to API
    const spinner = document.getElementById('recipe-upload-spinner');
    spinner.style.display = '';

    const base64 = e.target.result.split(',')[1];
    const mediaType = file.type || 'image/jpeg';

    try {
      const res = await fetch('/api/recipes/upload-image', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({image: base64, media_type: mediaType}),
      });
      spinner.style.display = 'none';
      if (!res.ok) {
        const err = await res.json();
        alert('Failed to parse recipe: ' + (err.error || 'Unknown error'));
        return;
      }
      const data = await res.json();
      openRecipeEditor(data.recipe, null);
    } catch (err) {
      spinner.style.display = 'none';
      alert('Error uploading image: ' + err.message);
    }
  };
  reader.readAsDataURL(file);
}

function openRecipeEditor(recipe, existingId) {
  editingRecipeId = existingId;
  editingRecipeData = recipe;

  ['recipes-list-view','recipes-detail-view','recipes-upload-view'].forEach(id =>
    document.getElementById(id).style.display = 'none');
  document.getElementById('recipes-edit-view').style.display = '';
  document.getElementById('recipe-edit-title').textContent =
    existingId ? 'Edit Recipe' : 'Review Recipe';

  document.getElementById('recipe-edit-name').value = recipe.name || '';
  document.getElementById('recipe-edit-tags').value = (recipe.tags || []).join(', ');
  document.getElementById('recipe-edit-prep').value = recipe.prep_time_min || '';
  document.getElementById('recipe-edit-cook').value = recipe.cook_time_min || '';
  document.getElementById('recipe-edit-servings').value = recipe.servings || '';

  const ingLines = (recipe.ingredients || []).map(i => {
    const parts = [i.quantity, i.unit, i.name].filter(Boolean);
    return parts.join(' ');
  });
  document.getElementById('recipe-edit-ingredients').value = ingLines.join('\\n');

  document.getElementById('recipe-edit-directions').value =
    (recipe.directions || []).join('\\n');
}

function editRecipe(id) {
  const recipe = allRecipes.find(r => r.id === id);
  if (recipe) openRecipeEditor(recipe, id);
}

function parseIngredientLine(line) {
  line = line.trim();
  if (!line) return null;
  // Try to parse "qty unit name" pattern
  const m = line.match(/^([\\d./]+(?:\\s*-\\s*[\\d./]+)?)\\s+(\\w+)\\s+(.+)$/);
  if (m) return {quantity: m[1], unit: m[2], name: m[3]};
  // Try "qty name" (no unit)
  const m2 = line.match(/^([\\d./]+)\\s+(.+)$/);
  if (m2) return {quantity: m2[1], unit: '', name: m2[2]};
  // Just a name
  return {quantity: '', unit: '', name: line};
}

async function saveRecipeEdit() {
  const name = document.getElementById('recipe-edit-name').value.trim();
  if (!name) { alert('Recipe name is required'); return; }

  const tags = document.getElementById('recipe-edit-tags').value
    .split(',').map(t => t.trim()).filter(Boolean);
  const prep = parseInt(document.getElementById('recipe-edit-prep').value) || null;
  const cook = parseInt(document.getElementById('recipe-edit-cook').value) || null;
  const servings = parseInt(document.getElementById('recipe-edit-servings').value) || null;

  const ingredients = document.getElementById('recipe-edit-ingredients').value
    .split('\\n').map(parseIngredientLine).filter(Boolean);
  const directions = document.getElementById('recipe-edit-directions').value
    .split('\\n').map(l => l.trim()).filter(Boolean);

  const recipe = {
    name, tags, prep_time_min: prep, cook_time_min: cook, servings,
    ingredients, directions,
    source: editingRecipeData ? (editingRecipeData.source || 'manual') : 'manual',
    raw_text: editingRecipeData ? (editingRecipeData.raw_text || '') : '',
  };

  try {
    const btn = document.getElementById('recipe-save-btn');
    btn.disabled = true;
    btn.textContent = 'Saving...';

    let res;
    if (editingRecipeId) {
      res = await fetch(`/api/recipes/${editingRecipeId}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(recipe),
      });
    } else {
      res = await fetch('/api/recipes', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(recipe),
      });
    }

    btn.disabled = false;
    btn.textContent = 'Save Recipe';

    if (!res.ok) {
      const err = await res.json();
      alert('Failed to save: ' + (err.error || 'Unknown error'));
      return;
    }

    showRecipesList();
  } catch (err) {
    document.getElementById('recipe-save-btn').disabled = false;
    document.getElementById('recipe-save-btn').textContent = 'Save Recipe';
    alert('Error saving recipe: ' + err.message);
  }
}

async function deleteRecipe(id, name) {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return;
  try {
    const res = await fetch(`/api/recipes/${id}`, {method: 'DELETE'});
    if (!res.ok) {
      const err = await res.json();
      alert('Failed to delete: ' + (err.error || 'Unknown error'));
      return;
    }
    showRecipesList();
  } catch (err) {
    alert('Error deleting recipe: ' + err.message);
  }
}
"""
