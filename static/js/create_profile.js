/**
 * Controls the 3-step Create Profile wizard:
 *   Step 1: Basic info + avatar preview
 *   Step 2: Role selection + interests chips (must pick >= 3)
 *   Step 3: Bio + live summary
 */

(() => {
    const $ = (id) => document.getElementById(id);

    // Toggle showing/hiding a small inline error block.
    function showErr(id, show) {
        const el = $(id);
        if (!el) return;
        el.classList.toggle("show", !!show);
    }

    /* =========================
       Wizard step control
    ========================= */
    let step = 1;

    /* Update which step section is visible + update progress dots/lines.
     * Also refresh summary when entering Step 3 */
    function setStep(n) {
        step = n;

        $("step1").style.display = n === 1 ? "block" : "none";
        $("step2").style.display = n === 2 ? "block" : "none";
        $("step3").style.display = n === 3 ? "block" : "none";

        // Progress UI (dots + connecting lines)
        const dot1 = $("dot1");
        const dot2 = $("dot2");
        const dot3 = $("dot3");
        const line1 = $("line1");
        const line2 = $("line2");

        dot1.classList.toggle("active", n >= 1);
        dot2.classList.toggle("active", n >= 2);
        dot3.classList.toggle("active", n >= 3);
        line1.classList.toggle("active", n >= 2);
        line2.classList.toggle("active", n >= 3);

        if (n === 3) refreshSummary();
    }

    /* Step button handler:
     * - Step 1 -> Step 2 only if Step 1 is valid
     * - Step 2 -> Step 3 only if Step 2 is valid */
    function nextStep() {
        if (step === 1) {
            if (!validateStep1()) return;
            setStep(2);
            return;
        }

        if (step === 2) {
            if (!validateStep2()) return;
            setStep(3);
            return;
        }
    }

    /* Back button handler:
     * - Step 2 -> Step 1
     * - Step 3 -> Step 2 */
    function prevStep() {
        if (step === 2) setStep(1);
        if (step === 3) setStep(2);
    }

    /* =========================
       Validation rule
    ========================= */

    /* .com-only email validation */
    function validEmailCom(v) {
        return /^[^\s@]+@[^\s@]+\.com$/i.test(v.trim());
    }

    /* Phone validation:
     * - Allow +, spaces, hyphens, parentheses
     * - Must contain 8–15 digits total */
    function validPhone(v) {
        const digits = v.replace(/\D/g, "");
        if (digits.length < 8 || digits.length > 15) return false;
        return /^[0-9+\-\s()]+$/.test(v.trim());
    }

    /* Validate Step 1 fields:
     * - First name, last name required
     * - Email must look like xxx@xxx.com
     * - Phone must pass digit-count + allowed characters rule
     * - DOB required (browser date input)
     * - Location required */
    function validateStep1() {
        const first = $("first_name").value.trim();
        const last = $("last_name").value.trim();
        const email = $("email").value.trim();
        const phone = $("phone").value.trim();
        const dob = $("dob").value.trim();
        const location = $("location").value.trim();

        let ok = true;

        showErr("err_first_name", !first);
        if (!first) ok = false;

        showErr("err_last_name", !last);
        if (!last) ok = false;

        if (!email || !validEmailCom(email)) {
            showErr("err_email", true);
            ok = false;
        } else {
            showErr("err_email", false);
        }

        if (!phone || !validPhone(phone)) {
            showErr("err_phone", true);
            ok = false;
        } else {
            showErr("err_phone", false);
        }

        showErr("err_dob", !dob);
        if (!dob) ok = false;

        showErr("err_location", !location);
        if (!location) ok = false;

        return ok;
    }

    /* Validate Step 2:
     * - Must choose role: "Young Person" or "Senior"
     * - Must select at least 3 interests */
    function validateStep2() {
        const role = $("role").value.trim();
        const interests = getSelectedInterests();

        let ok = true;

        showErr("err_role", !role);
        if (!role) ok = false;

        showErr("err_interests", interests.length < 3);
        if (interests.length < 3) ok = false;

        return ok;
    }

    /* =========================
       Role selection
    ========================= */

    /* Set role hidden input + update UI highlight.
     * Called by onclick in the role cards */
    function setRole(value) {
        $("role").value = value;

        $("roleYoung").classList.toggle("active", value === "Young Person");
        $("roleSenior").classList.toggle("active", value === "Senior");

        // Once picked, hide the error
        showErr("err_role", false);

        // If Step 3 is visible, summary updates too
        refreshSummary();
    }

    /* =========================
       Interests chips selection
    ========================= */

    // Interests
    const interestsList = [
        "Cooking", "Gardening", "Reading",
        "Music", "Art", "History",
        "Technology", "Travel", "Sports",
        "Photography", "Crafts", "Movies",
    ];

    // Use a Set to avoid duplicates and allow fast toggle.
    const selected = new Set();

    /* Render clickable chips into #chips container.
     * Each click toggles selected state and updates hidden input */
    function renderChips() {
        const wrap = $("chips");
        wrap.innerHTML = "";

        interestsList.forEach((name) => {
            const btn = document.createElement("div");
            btn.className = "chip";
            btn.textContent = name;

            if (selected.has(name)) btn.classList.add("active");

            btn.addEventListener("click", () => {
                if (selected.has(name)) selected.delete(name);
                else selected.add(name);

                btn.classList.toggle("active");
                updateSelectedCount();

                // Once user interacts, hide the "need 3 interests" error
                showErr("err_interests", false);

                refreshSummary();
            });

            wrap.appendChild(btn);
        });

        updateSelectedCount();
    }

    /* Updates:
     * - "Selected: X interests" label
     * - hidden input #interests used by backend */
    function updateSelectedCount() {
        const count = selected.size;
        $("selectedCount").textContent = `Selected: ${count} interests`;

        // This hidden input is what your Flask route reads
        $("interests").value = Array.from(selected).join(", ");
    }

    function getSelectedInterests() {
        return Array.from(selected);
    }

    /* =========================
       Bio count + Step 3 summary
    ========================= */

    /* Refresh the Step 3 summary box.
     * Called when:
     * - entering Step 3
     * - changing role
     * - selecting interests
     * - typing in bio */
    function refreshSummary() {
        const first = $("first_name").value.trim();
        const last = $("last_name").value.trim();
        const location = $("location").value.trim();
        const role = $("role").value.trim();

        $("sumName").textContent = (first || last) ? `${first} ${last}`.trim() : "-";
        $("sumLocation").textContent = location || "-";
        $("sumRole").textContent = role || "-";

        const pills = $("sumInterests");
        pills.innerHTML = "";

        getSelectedInterests().forEach((i) => {
            const p = document.createElement("span");
            p.className = "pill";
            p.textContent = i;
            pills.appendChild(p);
        });
    }

    /* Updates the live character counter under the bio textarea. */
    function updateBioCount() {
        const bio = $("bio");
        $("bioCount").textContent = bio.value.length;
    }

    /* =========================
       Avatar preview
    ========================= */

    /* When user selects an image file, show a preview in the circle.
     * This does NOT upload — upload happens on form submit */
    function wireAvatarPreview() {
        const avatar = $("avatar");
        if (!avatar) return;

        avatar.addEventListener("change", (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;

            const reader = new FileReader();
            reader.onload = () => {
                $("avatarPreview").src = reader.result;
            };
            reader.readAsDataURL(file);
        });
    }

    /* =========================
       Form submission behavior
    ========================= */

    /* Before submitting:
     * Ensure #interests hidden input matches the current Set.
     * (Mostly safe—this also protects against any weird DOM states.) */
    function wireFormSubmit() {
        const form = $("wizardForm");
        if (!form) return;

        form.addEventListener("submit", () => {
            $("interests").value = Array.from(selected).join(", ");
        });
    }

    /* Wire live updates for bio counter + summary. */
    function wireBioInput() {
        const bio = $("bio");
        if (!bio) return;

        bio.addEventListener("input", () => {
            updateBioCount();
            refreshSummary();
        });
    }

    /* =========================
       Prefill from session-rendered values
    ========================= */

    /* On page load:
     * - If profile.role exists, highlight correct role
     * - If profile.interests exists, pre-select chips
     * - Update bio counter and summary */
    function initPrefill() {
        // Role prefill (stored in hidden input)
        const roleVal = $("role").value.trim();
        if (roleVal) setRole(roleVal);

        // Interests prefill (stored in hidden input, comma-separated)
        const interestsVal = $("interests").value.trim();
        if (interestsVal) {
            interestsVal
                .split(",")
                .map((x) => x.trim())
                .filter(Boolean)
                .forEach((x) => selected.add(x));
        }
    }

    /* =========================
       Init
    ========================= */
    function init() {
        initPrefill();

        // Must run after initPrefill so chips show selected state
        renderChips();

        // Show correct bio count on load
        updateBioCount();

        // Keep summary synced with current values
        refreshSummary();

        wireAvatarPreview();
        wireFormSubmit();
        wireBioInput();

        // Always start at Step 1
        setStep(1);
    }

    document.addEventListener("DOMContentLoaded", init);

    window.nextStep = nextStep;
    window.prevStep = prevStep;
    window.setRole = setRole;
})();
