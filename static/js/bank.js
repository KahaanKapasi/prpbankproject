/* ============================================================
   PRP Bank – Main UI Script (vanilla JS, no dependencies)
   ============================================================ */

function fmtINR(n) {
    var num = parseFloat(n);
    if (isNaN(num)) return '₹0.00';
    var parts = num.toFixed(2).split('.');
    var intPart = parts[0];
    var decPart = parts[1];
    var sign = '';
    if (intPart[0] === '-') {
        sign = '-';
        intPart = intPart.slice(1);
    }
    if (intPart.length > 3) {
        var last3 = intPart.slice(-3);
        var rest = intPart.slice(0, -3);
        rest = rest.replace(/\B(?=(\d{2})+(?!\d))/g, ',');
        intPart = rest + ',' + last3;
    }
    return sign + '₹' + intPart + '.' + decPart;
}

function showToast(message, type) {
    type = type || 'success';
    var container = document.querySelector('.toast-container');
    if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        Object.assign(container.style, {
            position: 'fixed',
            bottom: '24px',
            right: '24px',
            zIndex: '9999',
            display: 'flex',
            flexDirection: 'column',
            gap: '8px',
            alignItems: 'flex-end'
        });
        document.body.appendChild(container);
    }

    var toast = document.createElement('div');
    toast.className = 'toast toast-' + type;
    Object.assign(toast.style, {
        padding: '12px 20px',
        borderRadius: '8px',
        color: '#fff',
        fontSize: '14px',
        fontWeight: '500',
        boxShadow: '0 4px 12px rgba(0,0,0,.15)',
        transform: 'translateX(120%)',
        opacity: '0',
        transition: 'transform .3s ease, opacity .3s ease',
        background: type === 'error' ? '#ef4444' : '#10b981',
        maxWidth: '360px',
        wordBreak: 'break-word'
    });
    toast.textContent = message;
    container.appendChild(toast);

    requestAnimationFrame(function () {
        toast.style.transform = 'translateX(0)';
        toast.style.opacity = '1';
    });

    setTimeout(function () {
        toast.style.transform = 'translateX(120%)';
        toast.style.opacity = '0';
        setTimeout(function () {
            if (toast.parentNode) toast.parentNode.removeChild(toast);
        }, 350);
    }, 3000);
}

/* ---- Main initialisation ---- */
document.addEventListener('DOMContentLoaded', function () {

    /* ----------------------------------------------------------
       1. Demo credential auto-fill (login page)
    ---------------------------------------------------------- */
    var credCards = document.querySelectorAll('.credential-card');
    credCards.forEach(function (card) {
        card.addEventListener('click', function () {
            credCards.forEach(function (c) { c.classList.remove('selected'); });
            card.classList.add('selected');

            var map = {
                'customer_id': card.getAttribute('data-customer-id'),
                'password':    card.getAttribute('data-password'),
                'account_number': card.getAttribute('data-account'),
                'ifsc_code':   card.getAttribute('data-ifsc'),
                'branch':      card.getAttribute('data-branch')
            };
            Object.keys(map).forEach(function (id) {
                var input = document.getElementById(id);
                if (input && map[id] !== null) {
                    input.value = map[id];
                    input.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        });
    });

    /* ----------------------------------------------------------
       2. Mobile sidebar toggle
    ---------------------------------------------------------- */
    var sidebar = document.querySelector('.sidebar');
    var menuToggle = document.querySelector('.menu-toggle');
    var overlay = document.querySelector('.mobile-overlay');

    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', function () {
            sidebar.classList.toggle('open');
        });
    }
    if (overlay && sidebar) {
        overlay.addEventListener('click', function () {
            sidebar.classList.remove('open');
        });
    }
    if (sidebar) {
        sidebar.querySelectorAll('.nav-item').forEach(function (item) {
            item.addEventListener('click', function () {
                if (window.innerWidth <= 768) {
                    sidebar.classList.remove('open');
                }
            });
        });
    }

    /* ----------------------------------------------------------
       3. User dropdown (topbar)
    ---------------------------------------------------------- */
    var dropTrigger = document.querySelector('.user-dropdown-trigger');
    var dropdown = document.querySelector('.user-dropdown');
    if (dropTrigger && dropdown) {
        dropTrigger.addEventListener('click', function (e) {
            e.stopPropagation();
            dropdown.classList.toggle('open');
        });
        document.addEventListener('click', function (e) {
            if (!dropdown.contains(e.target) && !dropTrigger.contains(e.target)) {
                dropdown.classList.remove('open');
            }
        });
    }

    /* ----------------------------------------------------------
       4. Tab switching
    ---------------------------------------------------------- */
    var tabs = document.querySelectorAll('.tab');
    tabs.forEach(function (tab) {
        tab.addEventListener('click', function () {
            var group = tab.parentElement;
            var name = tab.getAttribute('data-tab');
            if (!name) return;

            group.querySelectorAll('.tab').forEach(function (t) { t.classList.remove('active'); });
            tab.classList.add('active');

            var contentParent = group.parentElement;
            contentParent.querySelectorAll('.tab-content').forEach(function (tc) {
                tc.classList.remove('active');
            });
            var target = document.getElementById('tab-' + name);
            if (target) target.classList.add('active');
        });
    });

    /* ----------------------------------------------------------
       5. Table search / filter
    ---------------------------------------------------------- */
    document.querySelectorAll('.table-search').forEach(function (input) {
        input.addEventListener('input', function () {
            var query = input.value.toLowerCase().trim();
            var container = input.closest('.card') || input.closest('.table-wrapper') || input.parentElement;
            var table = container.querySelector('.inst-table') || container.querySelector('.table');
            if (!table) return;

            var rows = table.querySelectorAll('tbody tr');
            rows.forEach(function (row) {
                var text = row.textContent.toLowerCase();
                row.style.display = text.indexOf(query) !== -1 ? '' : 'none';
            });
        });
    });

    /* ----------------------------------------------------------
       6. Balance masking
    ---------------------------------------------------------- */
    var maskBtn = document.querySelector('.mask-toggle');
    if (maskBtn) {
        var masked = false;
        maskBtn.addEventListener('click', function () {
            var els = document.querySelectorAll('.maskable');
            masked = !masked;
            els.forEach(function (el) {
                if (masked) {
                    el.setAttribute('data-original', el.textContent);
                    el.textContent = '••••••';
                } else {
                    var orig = el.getAttribute('data-original');
                    if (orig !== null) el.textContent = orig;
                }
            });
        });
    }

    /* ----------------------------------------------------------
       7. Mini canvas chart (dashboard)
    ---------------------------------------------------------- */
    var canvas = document.getElementById('balance-chart');
    if (canvas) {
        var ctx = canvas.getContext('2d');
        var W = canvas.width || 200;
        var H = canvas.height || 60;
        canvas.width = W;
        canvas.height = H;

        var pts = [];
        var val = 40 + Math.random() * 10;
        for (var i = 0; i < 30; i++) {
            val += (Math.random() - 0.35) * 6;
            if (val < 5) val = 5;
            if (val > H - 5) val = H - 5;
            pts.push(val);
        }
        var min = Math.min.apply(null, pts);
        var max = Math.max.apply(null, pts);
        var range = max - min || 1;

        ctx.beginPath();
        ctx.strokeStyle = '#10b981';
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.lineCap = 'round';
        for (var j = 0; j < pts.length; j++) {
            var x = (j / (pts.length - 1)) * W;
            var y = H - 4 - ((pts[j] - min) / range) * (H - 8);
            if (j === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        var grad = ctx.createLinearGradient(0, 0, 0, H);
        grad.addColorStop(0, 'rgba(16,185,129,.18)');
        grad.addColorStop(1, 'rgba(16,185,129,0)');
        ctx.lineTo(W, H);
        ctx.lineTo(0, H);
        ctx.closePath();
        ctx.fillStyle = grad;
        ctx.fill();
    }

    /* ----------------------------------------------------------
       8. Config inline editing (admin)
    ---------------------------------------------------------- */
    document.querySelectorAll('.config-edit-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var row = btn.closest('tr') || btn.closest('.config-row') || btn.parentElement;
            var display = row.querySelector('.config-display');
            var input = row.querySelector('.config-input');
            if (display) display.style.display = 'none';
            if (input) input.style.display = '';
            btn.style.display = 'none';
            var saveBtn = row.querySelector('.config-save-btn');
            var cancelBtn = row.querySelector('.config-cancel-btn');
            if (saveBtn) saveBtn.style.display = '';
            if (cancelBtn) cancelBtn.style.display = '';
        });
    });

    document.querySelectorAll('.config-cancel-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var row = btn.closest('tr') || btn.closest('.config-row') || btn.parentElement;
            var display = row.querySelector('.config-display');
            var input = row.querySelector('.config-input');
            if (display) display.style.display = '';
            if (input) input.style.display = 'none';
            btn.style.display = 'none';
            var saveBtn = row.querySelector('.config-save-btn');
            var editBtn = row.querySelector('.config-edit-btn');
            if (saveBtn) saveBtn.style.display = 'none';
            if (editBtn) editBtn.style.display = '';
        });
    });

    document.querySelectorAll('.config-save-btn').forEach(function (btn) {
        btn.addEventListener('click', function () {
            var form = btn.closest('form');
            if (form) form.submit();
        });
    });

    /* ----------------------------------------------------------
       9. Feature flag toggles (admin)
    ---------------------------------------------------------- */
    document.querySelectorAll('.flag-toggle').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm('Are you sure you want to toggle this feature flag?')) {
                e.preventDefault();
                return;
            }
            var form = btn.closest('form');
            if (form) form.submit();
        });
    });

    /* ----------------------------------------------------------
       10. Seed confirmation (admin)
    ---------------------------------------------------------- */
    document.querySelectorAll('.seed-btn').forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            if (!confirm('This will seed the database with sample data. Continue?')) {
                e.preventDefault();
            } else {
                var form = btn.closest('form');
                if (form) form.submit();
            }
        });
    });

    /* ----------------------------------------------------------
       11. Auto-dismiss alerts
    ---------------------------------------------------------- */
    document.querySelectorAll('.alert').forEach(function (alert) {
        alert.style.transition = 'opacity .5s ease';
        setTimeout(function () {
            alert.style.opacity = '0';
            setTimeout(function () {
                if (alert.parentNode) alert.parentNode.removeChild(alert);
            }, 500);
        }, 5000);
    });

    /* ----------------------------------------------------------
       12. Smooth page load
    ---------------------------------------------------------- */
    document.body.classList.add('loaded');
});
