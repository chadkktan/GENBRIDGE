/**
 * - Edit Profile flow (edit/save/cancel + validation)
 * - Avatar preview (client-side only)
 * - Two-Factor toggle (UI demo)
 * - Change Password modal (UI demo validation)
 * - Start Over modal
 * - Sign Out / Delete confirmation modals
 * - Revoke active session (calls Flask/revoke-session)
 */

(() => {
    /* Helpers */
    const $ = (id) => document.getElementById(id);

    function showError(id, msg) {
        const el = $(id);
        if (!el) return;
        if (msg) el.textContent = msg;
        el.classList.add("show");
    }

    function clearError(id) {
        const el = $(id);
        if (!el) return;
        el.classList.remove("show");
    }

    function openOverlay(id) {
        const overlay = $(id);
        if (!overlay) return;
        overlay.classList.add("show");
        overlay.setAttribute("aria-hidden", "false");
    }

    function closeOverlay(id) {
        const overlay = $(id);
        if (!overlay) return;
        overlay.classList.remove("show");
        overlay.setAttribute("aria-hidden", "true");
    }

    /* Validation helpers */

    // UI enforces .com emails 
    function validateEmailCom(email) {
        return /^[^\s@]+@[^\s@]+\.com$/i.test(email.trim());
    }

    function validatePhone(phone) {
        const v = phone.trim();
        const digitsOnly = v.replace(/\D/g, "");
        if (digitsOnly.length < 8 || digitsOnly.length > 15) return false;
        return /^[0-9+\-\s()]+$/.test(v);
    }

    function isStrongPassword(pw) {
        // At least 8 chars, upper, lower, number, special
        const strong = /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/;
        return strong.test(pw);
    }

    /* Profile Edit/Save/Cancel */
    let editing = false;
    let originalValues = {};

    function setEditableState(on) {
        document.querySelectorAll(".editable-field").forEach((field) => {
            field.readOnly = !on;
            field.classList.toggle("editable", on);
        });
    }

    function startEdit() {
        editing = true;

        // Store current values so Cancel can restore them
        originalValues = {
            firstName: $("firstName")?.value ?? "",
            lastName: $("lastName")?.value ?? "",
            email: $("email")?.value ?? "",
            phone: $("phone")?.value ?? "",
            location: $("location")?.value ?? "",
            website: $("website")?.value ?? "",
            bio: $("bio")?.value ?? "",
        };

        setEditableState(true);

        $("cancelBtn").style.display = "inline-block";
        $("editBtn").textContent = "Save Profile";
        $("editBtn").className = "btn btn-red";
    }

    function saveEdit() {
        let ok = true;

        const first = $("firstName").value.trim();
        const last = $("lastName").value.trim();
        const email = $("email").value.trim();
        const phone = $("phone").value.trim();

        if (!first) {
            showError("errFirstName", "Please enter your first name.");
            ok = false;
        } else {
            clearError("errFirstName");
        }

        if (!last) {
            showError("errLastName", "Please enter your last name.");
            ok = false;
        } else {
            clearError("errLastName");
        }

        if (!email) {
            showError("errEmail", "Please enter your email address.");
            ok = false;
        } else if (!validateEmailCom(email)) {
            showError("errEmail", "Email must look like xxx@xxx.com");
            ok = false;
        } else {
            clearError("errEmail");
        }

        if (!phone) {
            showError("errPhone", "Please enter your phone number.");
            ok = false;
        } else if (!validatePhone(phone)) {
            showError("errPhone", "Please enter a valid phone number.");
            ok = false;
        } else {
            clearError("errPhone");
        }

        if (!ok) return;

        // Submit the existing profile form (posts to /update-profile)
        $("profileForm").submit();
    }

    function cancelEdit() {
        if (!editing) return;

        $("firstName").value = originalValues.firstName;
        $("lastName").value = originalValues.lastName;
        $("email").value = originalValues.email;
        $("phone").value = originalValues.phone;
        $("location").value = originalValues.location;
        $("website").value = originalValues.website;
        $("bio").value = originalValues.bio;

        editing = false;
        setEditableState(false);

        $("cancelBtn").style.display = "none";
        $("editBtn").textContent = "Edit Profile";
        $("editBtn").className = "btn btn-red";

        ["errFirstName", "errLastName", "errEmail", "errPhone"].forEach(clearError);
    }

    function onEditButtonClick() {
        if (!editing) startEdit();
        else saveEdit();
    }

    // Clears error messages as the user types (only while editing)
    function liveValidate() {
        if (!editing) return;

        if ($("firstName").value.trim()) clearError("errFirstName");
        if ($("lastName").value.trim()) clearError("errLastName");

        const e = $("email").value.trim();
        if (e && validateEmailCom(e)) clearError("errEmail");

        const p = $("phone").value.trim();
        if (p && validatePhone(p)) clearError("errPhone");
    }

    /* Start Over modal */
    function openStartOverModal() {
        $("startOverModal").classList.add("show");
    }

    function closeStartOverModal() {
        $("startOverModal").classList.remove("show");
    }

    function confirmStartOver() {
        // Goes to Flask route that clears profile and returns to create profile
        window.location.href = "/restart-profile";
    }

    /* Sign Out / Delete modals */
    function openSignOutModal() {
        openOverlay("signOutModal");
    }

    function openDeleteModal() {
        openOverlay("deleteModal");
    }

    function confirmSignOut() {
        // URL is injected by Jinja in profile.html
        window.location.href = window.__SIGN_OUT_URL__ || "/";
    }

    function confirmDeleteAccount() {
        // URL is injected by Jinja in profile.html
        window.location.href = window.__DELETE_ACCOUNT_URL__ || "/";
    }

    /*  Avatar preview (client-side) */
    function wireAvatarPreview() {
        const input = $("avatarInput");
        if (!input) return;

        input.addEventListener("change", (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = () => {
                const img = $("profileImage");
                if (img) img.src = reader.result;
            };
            reader.readAsDataURL(file);
        });
    }

    /* Two-Factor toggle (UI demo) */
    let twoFA = true;

    function render2FA() {
        if (twoFA) {
            $("twofaStatus").textContent = "Enabled via authenticator app";
            $("twofaBtn").textContent = "Disable";
            $("twofaBtn").className = "btn btn-outline";
        } else {
            $("twofaStatus").textContent = "Add an extra layer of security";
            $("twofaBtn").textContent = "Enable";
            $("twofaBtn").className = "btn btn-red";
        }
    }

    function toggle2FA() {
        twoFA = !twoFA;
        render2FA();
    }

    /* Change Password modal (UI demo) */
    function openChangePassword() {
        $("pwModal").classList.add("show");

        ["currentPw", "newPw", "confirmPw"].forEach((id) => {
            const el = $(id);
            if (el) el.value = "";
        });

        ["errCurrentPw", "errNewPw", "errConfirmPw"].forEach((id) => {
            const el = $(id);
            if (el) el.classList.remove("show");
        });
    }

    function closeChangePassword() {
        $("pwModal").classList.remove("show");
    }

    function toggleEye(inputId) {
        const input = $(inputId);
        if (!input) return;
        input.type = input.type === "password" ? "text" : "password";
    }

    function submitChangePassword(e) {
        e.preventDefault();

        const currentPw = $("currentPw").value.trim();
        const newPw = $("newPw").value;
        const confirmPw = $("confirmPw").value;

        let ok = true;

        if (!currentPw) {
            showError("errCurrentPw", "Please enter your current password.");
            ok = false;
        } else {
            clearError("errCurrentPw");
        }

        if (!newPw) {
            showError("errNewPw", "Please enter your new password.");
            ok = false;
        } else if (!isStrongPassword(newPw)) {
            showError("errNewPw", "Password must be strong (8+ chars, upper, lower, number, special).");
            ok = false;
        } else {
            clearError("errNewPw");
        }

        if (!confirmPw) {
            showError("errConfirmPw", "Please confirm your new password.");
            ok = false;
        } else if (confirmPw !== newPw) {
            showError("errConfirmPw", "Confirm password must match new password.");
            ok = false;
        } else {
            clearError("errConfirmPw");
        }

        if (!ok) return false;

        alert("Password updated (demo). Connect this to Flask POST if required.");
        closeChangePassword();
        return false;
    }

    /* Revoke Active Session  */
    async function revokeSession(sessionId) {
        const ok = confirm("Revoke this session?\n\nThat device will be signed out.");
        if (!ok) return;

        try {
            const res = await fetch("/revoke-session", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ session_id: sessionId }),
            });

            const data = await res.json();

            if (!data.ok) {
                alert(data.message || "Failed to revoke session.");
                return;
            }

            // If current session was revoked, backend tells us to redirect
            if (data.revoked_current && data.redirect) {
                window.location.href = data.redirect;
                return;
            }

            // Remove the card from UI
            const card = document.querySelector(`.session-card[data-sid="${sessionId}"]`);
            if (card) card.remove();
        } catch (err) {
            alert("Error revoking session.");
        }
    }

    /* Global click/keydown handlers
       - Click outside modals closes them
       - ESC closes modals */
    function wireModalCloseBehavior() {
        // Click outside these modals to close
        document.addEventListener("click", (e) => {
            const signOut = $("signOutModal");
            const del = $("deleteModal");
            const pw = $("pwModal");
            const so = $("startOverModal");

            if (signOut && signOut.classList.contains("show") && e.target === signOut) {
                closeOverlay("signOutModal");
            }

            if (del && del.classList.contains("show") && e.target === del) {
                closeOverlay("deleteModal");
            }

            if (pw && pw.classList.contains("show") && e.target === pw) {
                closeChangePassword();
            }

            if (so && so.classList.contains("show") && e.target === so) {
                closeStartOverModal();
            }
        });

        // ESC closes confirmation modals
        document.addEventListener("keydown", (e) => {
            if (e.key !== "Escape") return;
            closeOverlay("signOutModal");
            closeOverlay("deleteModal");
        });
    }

    /* Init */
    function init() {
        // Live validation while editing
        ["firstName", "lastName", "email", "phone"].forEach((id) => {
            const el = $(id);
            if (el) el.addEventListener("input", liveValidate);
        });

        wireAvatarPreview();
        wireModalCloseBehavior();

        // Initialize 2FA display
        render2FA();
    }

    document.addEventListener("DOMContentLoaded", init);

    /* Expose functions called by inline onclick=""
       (Because the HTML calls these directly) */
    window.onEditButtonClick = onEditButtonClick;
    window.cancelEdit = cancelEdit;

    window.openChangePassword = openChangePassword;
    window.closeChangePassword = closeChangePassword;
    window.toggleEye = toggleEye;
    window.submitChangePassword = submitChangePassword;

    window.toggle2FA = toggle2FA;

    window.openStartOverModal = openStartOverModal;
    window.closeStartOverModal = closeStartOverModal;
    window.confirmStartOver = confirmStartOver;

    window.openSignOutModal = openSignOutModal;
    window.openDeleteModal = openDeleteModal;

    // These are used by the modal buttons
    window.confirmSignOut = confirmSignOut;
    window.confirmDeleteAccount = confirmDeleteAccount;

    // Used by active sessions revoke link
    window.revokeSession = revokeSession;

    // Also expose closeModal/openModal if you still use them in HTML
    window.openModal = openOverlay;
    window.closeModal = closeOverlay;
})();
