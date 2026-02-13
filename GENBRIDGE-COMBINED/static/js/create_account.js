
/**
 * - Show/Hide password (eye icon)
 * - Sign-in modal open/close + ESC + click outside
 * - Create account form validation (strength + confirm match)
 * - Sign-in form validation
 * - Toast auto-remove
 * - Auto-open sign-in modal when backend requests it
 */

(function () {
  // ---------------------------
  // Helpers used by inline onclick=""
  // Attached them to window so the HTML can call them.
  // ---------------------------

  window.togglePassword = function (inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    input.type = input.type === "password" ? "text" : "password";
  };

  window.openSignInModal = function () {
    const overlay = document.getElementById("signInModal");
    if (!overlay) return;
    overlay.classList.add("show");
    overlay.setAttribute("aria-hidden", "false");
  };

  window.closeSignInModal = function () {
    const overlay = document.getElementById("signInModal");
    if (!overlay) return;
    overlay.classList.remove("show");
    overlay.setAttribute("aria-hidden", "true");
  };

  // ---------------------------
  // Validation rules
  // ---------------------------

  function isStrongPassword(pw) {
    // 8+ chars, uppercase, lowercase, number, special character
    return /^(?=.*[a-z])(?=.*[A-Z])(?=.*[0-9])(?=.*[^A-Za-z0-9]).{8,}$/.test(pw);
  }

  // ---------------------------
  // DOM ready init
  // ---------------------------
  document.addEventListener("DOMContentLoaded", () => {
    // ---- Close modal when clicking outside it ----
    document.addEventListener("click", (e) => {
      const overlay = document.getElementById("signInModal");
      if (overlay && overlay.classList.contains("show") && e.target === overlay) {
        window.closeSignInModal();
      }
    });

    // ---- ESC closes sign-in modal ----
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") window.closeSignInModal();
    });

    // ---- Sign-in form: use browser tooltip validation ----
    const signInForm = document.getElementById("signInForm");
    if (signInForm) {
      signInForm.addEventListener("submit", (e) => {
        if (!signInForm.checkValidity()) {
          e.preventDefault();
          signInForm.reportValidity();
        }
      });
    }

    // ---- Create Account form validation ----
    const form = document.getElementById("createAccountForm");
    const pwInput = document.getElementById("password");
    const cpwInput = document.getElementById("confirmPassword");

    // Clear custom errors while typing (prevents "stuck" messages)
    if (pwInput) pwInput.addEventListener("input", () => pwInput.setCustomValidity(""));
    if (cpwInput) cpwInput.addEventListener("input", () => cpwInput.setCustomValidity(""));

    if (form && pwInput && cpwInput) {
      form.addEventListener("submit", (e) => {
        // Clear old messages first
        pwInput.setCustomValidity("");
        cpwInput.setCustomValidity("");

        // 1) required fields + browser validity
        if (!form.checkValidity()) {
          e.preventDefault();
          form.reportValidity();
          return;
        }

        // 2) password strength
        if (!isStrongPassword(pwInput.value)) {
          e.preventDefault();
          pwInput.setCustomValidity(
            "Password must be at least 8 characters and include: uppercase, lowercase, number, and a special character."
          );
          pwInput.reportValidity();
          return;
        }

        // 3) confirm password match
        if (pwInput.value !== cpwInput.value) {
          e.preventDefault();
          cpwInput.setCustomValidity("Does not match password");
          cpwInput.reportValidity();
          return;
        }
      });
    }

    // ---- Toast auto-remove after fade ----
    const t = document.getElementById("gbToast");
    if (t) {
      setTimeout(() => t.remove(), 4100);
    }

    // ---- Auto-open sign-in modal if backend requested it ----
    // Pass this via <body data-open-signin="1|0">
    const shouldOpen = document.body && document.body.dataset.openSignin === "1";
    if (shouldOpen) window.openSignInModal();
  });
})();
