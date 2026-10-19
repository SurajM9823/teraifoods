(() => {
  'use strict';

  const embedded = window.parent !== window;
  const notify = (type, extra = {}) => {
    if (embedded) {
      window.parent.postMessage({ type, ...extra }, window.location.origin);
    } else if (type === 'terai-auth-complete') {
      window.location.assign('/');
    }
  };

  if (embedded) {
    document.documentElement.classList.add('embedded-auth');

    document.querySelector('.auth-close')?.addEventListener('click', (event) => {
      event.preventDefault();
      notify('terai-auth-close');
    });

    document.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') notify('terai-auth-close');
    });

    const card = document.querySelector('.auth-card');
    if (card) {
      new ResizeObserver(() => {
        notify('terai-auth-size', { height: card.scrollHeight + 10 });
      }).observe(card);
    }

    // If loaded on profile or success view, immediately notify completion
    if (window.location.pathname === '/manage-profile/' || window.location.pathname === '/') {
      notify('terai-auth-complete');
    }

    // Google authorization cannot run inside an iframe
    document.querySelectorAll('form[action*="/google/"]').forEach((form) => {
      form.target = '_top';
    });
  }

  function initPasswordToggles() {
    document.querySelectorAll('input[type="password"]').forEach((input) => {
      if (input.dataset.hasToggle) return;
      input.dataset.hasToggle = 'true';

      const wrapper = document.createElement('div');
      wrapper.className = 'password-wrapper';
      input.before(wrapper);
      wrapper.append(input);

      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'password-toggle';
      toggle.textContent = 'Show';
      toggle.setAttribute('aria-label', 'Show password');
      toggle.setAttribute('aria-pressed', 'false');

      toggle.addEventListener('click', () => {
        const reveal = input.type === 'password';
        input.type = reveal ? 'text' : 'password';
        toggle.textContent = reveal ? 'Hide' : 'Show';
        toggle.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
        toggle.setAttribute('aria-pressed', String(reveal));
      });

      wrapper.append(toggle);
    });
  }

  function initPasswordLiveValidation() {
    const pwdInput = document.querySelector('input[name="password1"], input[name="password"]');
    const confirmInput = document.querySelector('input[name="password2"]');
    const lenFeedback = document.getElementById('pwd-len-feedback');
    const matchFeedback = document.getElementById('pwd-match-feedback');

    if (!pwdInput) return;

    function updateValidation() {
      const pwdVal = pwdInput.value || '';
      const confirmVal = confirmInput ? confirmInput.value : '';

      if (lenFeedback) {
        if (pwdVal.length >= 12) {
          lenFeedback.className = 'pwd-feedback valid';
          lenFeedback.querySelector('.status-icon').textContent = '✓';
        } else if (pwdVal.length > 0) {
          lenFeedback.className = 'pwd-feedback invalid';
          lenFeedback.querySelector('.status-icon').textContent = '✕';
        } else {
          lenFeedback.className = 'pwd-feedback';
          lenFeedback.querySelector('.status-icon').textContent = '○';
        }
      }

      if (matchFeedback && confirmInput) {
        if (confirmVal.length > 0) {
          if (confirmVal === pwdVal && pwdVal.length >= 12) {
            matchFeedback.className = 'pwd-feedback valid';
            matchFeedback.querySelector('.status-icon').textContent = '✓';
          } else {
            matchFeedback.className = 'pwd-feedback invalid';
            matchFeedback.querySelector('.status-icon').textContent = '✕';
          }
        } else {
          matchFeedback.className = 'pwd-feedback';
          matchFeedback.querySelector('.status-icon').textContent = '○';
        }
      }
    }

    pwdInput.addEventListener('input', updateValidation);
    if (confirmInput) {
      confirmInput.addEventListener('input', updateValidation);
    }
  }

  function initOtpBoxes() {
    const originalInput = document.querySelector('input[name="code"], input[autocomplete="one-time-code"]');
    if (!originalInput) return;

    // Avoid duplicate containers
    const existingGroup = document.querySelector('.otp-boxes');
    if (existingGroup) existingGroup.remove();

    originalInput.style.position = 'absolute';
    originalInput.style.opacity = '0';
    originalInput.style.pointerEvents = 'none';
    originalInput.style.height = '0';
    originalInput.style.width = '0';

    const container = document.createElement('div');
    container.className = 'otp-boxes';
    container.setAttribute('role', 'group');
    container.setAttribute('aria-label', '6-digit verification code');

    const boxes = [];
    const initialDigits = (originalInput.value || '').replace(/\D/g, '').slice(0, 6);

    for (let i = 0; i < 6; i++) {
      const box = document.createElement('input');
      box.type = 'text';
      box.inputMode = 'numeric';
      box.pattern = '[0-9]*';
      box.maxLength = 1;
      box.className = 'otp-box';
      box.setAttribute('data-index', String(i));
      box.setAttribute('autocomplete', i === 0 ? 'one-time-code' : 'off');
      box.value = initialDigits[i] || '';
      if (box.value) box.classList.add('filled');

      box.addEventListener('input', (e) => {
        const raw = e.target.value.replace(/\D/g, '');
        if (raw.length > 1) {
          // Paste or multi-digit autofill
          distributeOtp(raw, i);
          return;
        }
        box.value = raw;
        box.classList.toggle('filled', Boolean(raw));
        syncOtp();
        if (raw && i < 5) {
          boxes[i + 1].focus();
          boxes[i + 1].select();
        }
      });

      box.addEventListener('keydown', (e) => {
        if (e.key === 'Backspace') {
          if (!box.value && i > 0) {
            boxes[i - 1].focus();
            boxes[i - 1].value = '';
            boxes[i - 1].classList.remove('filled');
            syncOtp();
            e.preventDefault();
          } else {
            box.value = '';
            box.classList.remove('filled');
            syncOtp();
          }
        } else if (e.key === 'ArrowLeft' && i > 0) {
          boxes[i - 1].focus();
        } else if (e.key === 'ArrowRight' && i < 5) {
          boxes[i + 1].focus();
        }
      });

      box.addEventListener('paste', (e) => {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData).getData('text');
        const digits = pasted.replace(/\D/g, '').slice(0, 6);
        distributeOtp(digits, i);
      });

      container.append(box);
      boxes.push(box);
    }

    function distributeOtp(digits, startIndex) {
      if (!digits) return;
      let digitIdx = 0;
      for (let j = 0; j < 6; j++) {
        if (j >= startIndex && digitIdx < digits.length) {
          boxes[j].value = digits[digitIdx++];
          boxes[j].classList.add('filled');
        }
      }
      syncOtp();
      const nextFocus = Math.min(startIndex + digits.length, 5);
      boxes[nextFocus].focus();
    }

    function syncOtp() {
      const code = boxes.map((b) => b.value).join('');
      originalInput.value = code;
      originalInput.dispatchEvent(new Event('input', { bubbles: true }));
      originalInput.dispatchEvent(new Event('change', { bubbles: true }));
    }

    originalInput.before(container);

    // Auto-focus first empty box
    const firstEmpty = boxes.find((b) => !b.value) || boxes[0];
    setTimeout(() => firstEmpty?.focus(), 150);
  }

  function initFormSubmit() {
    const form = document.getElementById('auth-form') || document.querySelector('.auth-card form:not([action*="/google/"]):not(#resend-form):not(#logout-from-stage)');
    if (!form || form.dataset.hasAjax) return;
    form.dataset.hasAjax = 'true';

    form.addEventListener('submit', async (e) => {
      // Live validation check for passwords before posting
      const pwdInput = form.querySelector('input[name="password1"]');
      const confirmInput = form.querySelector('input[name="password2"]');
      if (pwdInput && pwdInput.value.length < 12) {
        e.preventDefault();
        showInlineError('Password must be at least 12 characters long.');
        pwdInput.focus();
        return;
      }
      if (pwdInput && confirmInput && pwdInput.value !== confirmInput.value) {
        e.preventDefault();
        showInlineError('Passwords do not match. Please verify both fields.');
        confirmInput.focus();
        return;
      }

      // Check OTP code length if OTP form
      const codeInput = form.querySelector('input[name="code"], input[autocomplete="one-time-code"]');
      if (codeInput && codeInput.value.replace(/\D/g, '').length < 6) {
        e.preventDefault();
        showInlineError('Please enter all 6 digits of the verification code.');
        document.querySelectorAll('.otp-box').forEach(b => b.classList.add('is-invalid'));
        setTimeout(() => document.querySelectorAll('.otp-box').forEach(b => b.classList.remove('is-invalid')), 1200);
        return;
      }

      e.preventDefault();
      const submitBtn = form.querySelector('button[type="submit"]');
      const origHtml = submitBtn ? submitBtn.innerHTML : '';
      if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner"></span> Verifying...';
      }

      try {
        const formData = new FormData(form);
        const response = await fetch(form.action, {
          method: 'POST',
          body: formData,
          credentials: 'same-origin',
        });

        // If redirect occurred or response URL is home / profile
        const targetUrl = response.url || '';
        if (response.redirected || targetUrl.includes('/manage-profile') || targetUrl.endsWith('/')) {
          const path = new URL(targetUrl, window.location.origin).pathname;
          if (response.ok && (path === '/' || path === '/manage-profile/')) {
            notify('terai-auth-complete');
            return;
          }
          // If redirected to another step (like code verification)
          const nextHtml = await fetch(targetUrl).then(r => r.text());
          renderNewCard(nextHtml);
          return;
        }

        const html = await response.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');

        renderNewCard(html);
      } catch (err) {
        console.error('Submission error:', err);
        showInlineError('A network error occurred. Please try again.');
        if (submitBtn) {
          submitBtn.disabled = false;
          submitBtn.innerHTML = origHtml;
        }
      }
    });
  }

  function renderNewCard(html) {
    const parser = new DOMParser();
    const doc = parser.parseFromString(html, 'text/html');
    const newCard = doc.querySelector('.auth-card');
    const curCard = document.querySelector('.auth-card');

    if (newCard && curCard) {
      curCard.innerHTML = newCard.innerHTML;
      initAll();
    } else {
      window.location.reload();
    }
  }

  function showInlineError(message) {
    let errBox = document.querySelector('.form-errors');
    if (!errBox) {
      errBox = document.createElement('div');
      errBox.className = 'form-errors';
      const form = document.querySelector('.auth-form');
      if (form) form.prepend(errBox);
    }
    errBox.textContent = message;
    errBox.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function initAll() {
    initPasswordToggles();
    initPasswordLiveValidation();
    initOtpBoxes();
    initFormSubmit();

    const card = document.querySelector('.auth-card');
    if (card && embedded) {
      notify('terai-auth-size', { height: card.scrollHeight + 10 });
    }
  }

  // Initialize on DOM load
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
})();
