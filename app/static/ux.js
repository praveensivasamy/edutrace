document.addEventListener("submit", event => {
  const form = event.target.closest("form[data-busy-form]");
  if (!form) {
    return;
  }

  const formId = form.id;
  const submitButtons = [
    ...form.querySelectorAll('button[type="submit"], input[type="submit"]'),
    ...(formId
      ? document.querySelectorAll(`button[form="${formId}"], input[type="submit"][form="${formId}"]`)
      : [])
  ];
  const busyText = form.dataset.busyText || "Working...";

  submitButtons.forEach(button => {
    if (!button.dataset.originalText) {
      button.dataset.originalText = button.tagName === "INPUT" ? button.value : button.innerHTML;
    }
    button.disabled = true;
    if (button.tagName === "INPUT") {
      button.value = busyText;
      return;
    }
    button.innerHTML = `<span class="inline-flex items-center gap-2"><span class="spinner"></span><span>${busyText}</span></span>`;
  });
});

(() => {
  const storageKey = "edutrace-chart-variant";
  const select = document.getElementById("chart-variant-select");
  if (!select) {
    return;
  }

  let currentValue = "academic";
  try {
    const saved = window.localStorage.getItem(storageKey);
    if (saved) {
      currentValue = saved;
    }
  } catch (_) {
    currentValue = "academic";
  }
  select.value = currentValue;

  select.addEventListener("change", () => {
    try {
      window.localStorage.setItem(storageKey, select.value);
    } catch (_) {
      return;
    }
    window.location.reload();
  });
})();
