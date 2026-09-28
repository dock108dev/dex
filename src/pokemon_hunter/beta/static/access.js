'use strict';
const fragment = location.hash.slice(1);
history.replaceState(null, '', '/access/');
const parts = fragment.split('/');
if (parts.length === 3 && ['invite', 'recovery'].includes(parts[0]) && parts.slice(1).every(p => /^[A-Za-z0-9_-]+$/.test(p))) {
  const form = document.getElementById('access-form');
  ['kind', 'uid', 'token'].forEach((name, index) => { form.elements[name].value = parts[index]; });
  document.getElementById('message').textContent = 'Checking your private access link…';
  form.submit();
}
