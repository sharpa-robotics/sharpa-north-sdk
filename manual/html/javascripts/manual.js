// Clipboard API can be restricted for local files; retain copy support offline.
document.addEventListener('click', function(event) {
  const button = event.target.closest('.md-code__button');
  if (!button || window.isSecureContext && navigator.clipboard) return;
  const code = button.closest('.highlight, pre').querySelector('code');
  if (!code) return;
  const text = document.createElement('textarea');
  text.value = code.textContent;
  document.body.appendChild(text); text.select();
  document.execCommand('copy'); text.remove();
});
