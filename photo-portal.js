"use strict";
let photos = [];
let slide_show_on = false;
let slideTimer = null;
let slideGeneration = 0;
let slideIndex = 0;
let displayedName = null;
const imageURL = name => '/static/images/photos/' + encodeURIComponent(name);

async function fetchPhotos() {
  const response = await fetch('/photos', {cache: 'no-store'});
  if (!response.ok) throw new Error('Unable to retrieve photos.');
  return (await response.json()).photos.map(item => JSON.parse(item));
}
function statusMessage(text) { document.getElementById('status_string').textContent = text; }

// Requirement 4.2: synchronize both lists, preserving the selected radio button.
function syncPhotos(current) {
  photos = current;
  const present_thumbnail_photo_list = current.map(p => p.name + '-thumbnail-li');
  const present_photo_anchor_list = current.map(p => p.name + '-photo-anchor');
  for (const [list, ids] of [['available_photos_list', present_thumbnail_photo_list], ['photo_list', present_photo_anchor_list]]) {
    for (const child of Array.from(document.getElementById(list).children)) {
      if (!ids.includes(child.id)) child.remove();
    }
  }
  for (const photo of current) {
    if (!document.getElementById(photo.name + '-photo-anchor')) {
      const li = document.createElement('li');
      li.id = photo.name + '-photo-anchor';
      li.dataset.name = photo.name;
      if (document.body.dataset.user === 'admin') {
        const radio = document.createElement('input');
        radio.type = 'radio'; radio.name = 'photo_name'; radio.value = photo.name;
        radio.setAttribute('aria-label', 'Select ' + photo.name);
        li.append(radio);
      }
      const link = document.createElement('a');
      link.href = '#'; link.dataset.photoLink = photo.name; link.textContent = photo.name;
      li.append(link); document.getElementById('photo_list').append(li);
    }
    if (!document.getElementById(photo.name + '-thumbnail-li')) {
      const li = document.createElement('li'); li.id = photo.name + '-thumbnail-li'; li.dataset.name = photo.name;
      const figure = document.createElement('figure');
      const img = document.createElement('img'); img.src = imageURL(photo.name); img.alt = photo.name; img.dataset.preview = photo.name;
      const caption = document.createElement('figcaption'); caption.textContent = photo.name;
      figure.append(img, caption); li.append(figure); document.getElementById('available_photos_list').append(li);
    }
  }
  if (displayedName) {
    const photo = current.find(p => p.name === displayedName);
    if (photo) show_photo_details(photo.name, photo.date_taken, photo.tags);
    else { displayedName = null; document.getElementById('photo-details').replaceChildren(); }
  }
  const slide = document.querySelector('#slideshowImage figure');
  if (slide && !current.some(p => p.name === slide.dataset.name)) document.getElementById('slideshowImage').replaceChildren();
  const preview = document.getElementById('imageModal');
  if (preview.open && !current.some(p => p.name === preview.dataset.name)) preview.close();
}
async function make_photos_call() {
  try { syncPhotos(await fetchPhotos()); } catch (error) { console.error(error); }
}

// Requirements 5.1 / 5.2. A generation token invalidates requests already in flight.
async function start_slide_show() {
  stop_slide_show();
  slide_show_on = true;
  slideIndex = 0;
  const generation = slideGeneration;
  async function next() {
    try {
      const current = await fetchPhotos();
      if (!slide_show_on || generation !== slideGeneration) return;
      syncPhotos(current);
      if (current.length) {
        display_photo(slideIndex % current.length, current);
        slideIndex = (slideIndex + 1) % current.length;
      } else document.getElementById('slideshowImage').textContent = 'No photos available.';
    } catch (error) {
      if (generation === slideGeneration) statusMessage(error.message);
    }
    if (slide_show_on && generation === slideGeneration) slideTimer = setTimeout(next, 3000);
  }
  await next();
}
function display_photo(index, photo_images) {
  const photo = typeof photo_images[index] === 'string' ? JSON.parse(photo_images[index]) : photo_images[index];
  if (!photo) return;
  const figure = document.createElement('figure'); figure.id = 'big-img'; figure.dataset.name = photo.name;
  const img = document.createElement('img'); img.src = imageURL(photo.name); img.alt = photo.name;
  const caption = document.createElement('figcaption'); caption.textContent = photo.name;
  figure.append(img, caption); document.getElementById('slideshowImage').replaceChildren(figure);
}
function stop_slide_show() {
  slide_show_on = false; slideGeneration += 1; clearTimeout(slideTimer); slideTimer = null;
}

// Requirement 3.3: retrieve current tags via the REST API before opening the modal.
async function handle_update_delete_form(action) {
  const selected = document.querySelector('#update_delete_form input[name="photo_name"]:checked');
  if (!selected) return;
  if (action === 'delete') { document.getElementById('update_delete_form').submit(); return; }
  try {
    const response = await fetch('/photos/' + encodeURIComponent(selected.value) + '/tags', {cache: 'no-store'});
    if (!response.ok) throw new Error('Unable to retrieve tags.');
    const data = await response.json();
    document.getElementById('tags-photo-name').textContent = selected.value;
    document.getElementById('tags-photo-input').value = selected.value;
    document.getElementById('current-tags').textContent = data.tags;
    document.getElementById('new-tags').value = '';
    document.getElementById('tagsModal').showModal();
  } catch (error) { statusMessage(error.message); }
}
function show_photo_details(name, date_taken, tags) {
  displayedName = name;
  const target = document.getElementById('photo-details'); target.replaceChildren();
  for (const [label, value] of [['Photo', name], ['Date taken', date_taken], ['Tags', tags]]) {
    const line = document.createElement('p'); line.textContent = label + ': ' + (value || ''); target.append(line);
  }
}
function preview_photo(name) {
  const img = document.createElement('img'); img.src = imageURL(name); img.alt = name; img.id = 'preview-image';
  document.getElementById('image-modal-body').replaceChildren(img);
  const modal = document.getElementById('imageModal'); modal.dataset.name = name; modal.showModal();
}
function logout() { document.getElementById('settings-and-logout-form').submit(); }

document.addEventListener('DOMContentLoaded', () => {
  syncPhotos(JSON.parse(document.getElementById('initial-photos').textContent));
  document.addEventListener('click', event => {
    const link = event.target.closest('[data-photo-link]');
    if (link) {
      event.preventDefault(); const photo = photos.find(p => p.name === link.dataset.photoLink);
      if (photo) show_photo_details(photo.name, photo.date_taken, photo.tags);
    }
    const preview = event.target.closest('[data-preview]');
    if (preview) preview_photo(preview.dataset.preview);
  });
  for (const [id, action] of [['delete-photo', 'delete'], ['update-tags', 'update']]) {
    document.getElementById(id)?.addEventListener('click', event => { event.preventDefault(); handle_update_delete_form(action); });
  }
  // Poll after each response so requests cannot accumulate or arrive out of order.
  async function poll() { await make_photos_call(); setTimeout(poll, 5000); }
  setTimeout(poll, 5000);
});
