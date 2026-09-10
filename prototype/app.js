// Niravaan - Main Application JavaScript

// ============================================
// DATA
// ============================================
const blockData = {
    engineering: [
        { id: 'ENG-001', route: 'Mumbai Central - Virar', time: '02:00-05:00', type: 'Track Renewal', priority: 'high' },
        { id: 'ENG-002', route: 'Thane - Kalyan', time: '22:00-01:00', type: 'Point Machine', priority: 'critical' },
        { id: 'ENG-003', route: 'Dadar - Thane', time: '01:00-04:00', type: 'Rail Grinding', priority: 'medium' },
        { id: 'ENG-004', route: 'Borivali - Virar', time: '03:00-06:00', type: 'Ballast Cleaning', priority: 'low' },
    ],
    traction: [
        { id: 'TRD-001', route: 'Mumbai CST - Thane', time: '00:30-03:30', type: 'OHE Replacement', priority: 'critical' },
        { id: 'TRD-002', route: 'Kalyan - Pune', time: '02:00-05:00', type: 'Feeder Maintenance', priority: 'high' },
        { id: 'TRD-003', route: 'Dadar - Kalyan', time: '01:00-04:00', type: 'Insulator Check', priority: 'medium' },
    ],
    signal: [
        { id: 'SIG-001', route: 'Churchgate - Mumbai CST', time: '02:00-05:00', type: 'Relay Replacement', priority: 'high' },
        { id: 'SIG-002', route: 'Thane - Diva', time: '01:00-04:00', type: 'Track Circuit', priority: 'critical' },
        { id: 'SIG-003', route: 'Kalyan - Karjat', time: '03:00-06:00', type: 'Signal Wiring', priority: 'medium' },
    ]
};

const corridorData = [
    { id: 'COR-001', route: 'Mumbai - Delhi (Rajdhani)', length: '1,384 km', blocks: 12, availability: '92%', status: 'active' },
    { id: 'COR-002', route: 'Mumbai - Pune', length: '120 km', blocks: 8, availability: '87%', status: 'active' },
    { id: 'COR-003', route: 'Mumbai - Nashik', length: '167 km', blocks: 6, availability: '94%', status: 'active' },
    { id: 'COR-004', route: 'Thane - Kalyan', length: '28 km', blocks: 3, availability: '78%', status: 'maintenance' },
    { id: 'COR-005', route: 'Dadar - Bandra', length: '6 km', blocks: 2, availability: '95%', status: 'active' },
    { id: 'COR-006', route: 'Kalyan - Pune', length: '95 km', blocks: 5, availability: '89%', status: 'blocked' },
];

const defectsData = [
    { id: 'DEF-001', title: 'Rail Wear Exceeding Limit', dept: 'engineering', priority: 'critical', desc: 'Rail head wear on Track 2 near Thane station exceeds 6mm limit. Immediate renewal required.', location: 'Track 2, Km 124+300', date: '2026-09-08' },
    { id: 'DEF-002', title: 'OHE Wire Sagging', dept: 'traction', priority: 'critical', desc: 'Overhead equipment wire sag detected near Kalyan junction. Affecting pantograph contact.', location: 'OHE Line 3, Km 89+150', date: '2026-09-07' },
    { id: 'DEF-003', title: 'Signal Light Failure', dept: 'signal', priority: 'high', desc: 'Home signal at Thane station showing intermittent red. Relay inspection needed.', location: 'Signal TH-12', date: '2026-09-06' },
    { id: 'DEF-004', title: 'Point Machine Misalignment', dept: 'engineering', priority: 'high', desc: 'Point machine No. 5 at Dadar showing alignment error of 2mm. Needs calibration.', location: 'Point 5, Dadar', date: '2026-09-05' },
    { id: 'DEF-005', title: 'Feeder Trip Issue', dept: 'traction', priority: 'medium', desc: 'Recurrent tripping at Feeder Station 4. Capacitor bank inspection required.', location: 'Feeder 4, Km 56+200', date: '2026-09-04' },
    { id: 'DEF-006', title: 'Track Circuit Faulty', dept: 'signal', priority: 'high', desc: 'Track circuit T-8 showing false occupied status. Needs relay and bonding check.', location: 'Track Circuit T-8, Virar', date: '2026-09-03' },
    { id: 'DEF-007', title: 'Ballast Deficiency', dept: 'engineering', priority: 'low', desc: 'Ballast depth below required level on Track 1 between Borivali and Malad.', location: 'Track 1, Km 34+500', date: '2026-09-02' },
    { id: 'DEF-008', title: 'Insulator Contamination', dept: 'traction', priority: 'medium', desc: 'Porcelain insulators near Virar depot showing contamination. Cleaning needed.', location: 'OHE Km 112+800', date: '2026-09-01' },
    { id: 'DEF-009', title: 'Bonding Wire Damage', dept: 'signal', priority: 'low', desc: 'Rail bonding wire damaged at crossing section. Affects return current path.', location: 'Crossing Km 78+400', date: '2026-08-30' },
];

const activities = [
    { type: 'ai', icon: 'fa-brain', text: 'AI recommended merging 3 Engineering blocks in Sector A to save 4.5 hours', time: '5 min ago' },
    { type: 'success', icon: 'fa-check', text: 'Block ENG-001 approved by TPC. Scheduled for Sep 10, 02:00-05:00', time: '18 min ago' },
    { type: 'alert', icon: 'fa-exclamation', text: 'Critical defect DEF-001 requires immediate block allocation', time: '1 hour ago' },
    { type: 'ai', icon: 'fa-brain', text: 'AI suggests rescheduling OHE maintenance to night slot for 0% train impact', time: '2 hours ago' },
    { type: 'success', icon: 'fa-check', text: 'Integrated block TRD-001 + SIG-002 approved for Corridor B', time: '3 hours ago' },
];

// ============================================
// NAVIGATION
// ============================================
document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', (e) => {
        e.preventDefault();
        const section = item.dataset.section;
        
        // Update nav
        document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
        item.classList.add('active');
        
        // Update section
        document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
        document.getElementById(section).classList.add('active');
        
        // Update title
        document.getElementById('pageTitle').textContent = item.querySelector('span').textContent;
    });
});

// ============================================
// CHARTS
// ============================================
function initCharts() {
    // Utilization Chart
    const ctx1 = document.getElementById('utilizationChart');
    if (ctx1) {
        new Chart(ctx1, {
            type: 'line',
            data: {
                labels: ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
                datasets: [
                    {
                        label: 'Engineering',
                        data: [65, 72, 68, 75, 80, 78, 70],
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Traction',
                        data: [55, 60, 58, 62, 68, 65, 58],
                        borderColor: '#f59e0b',
                        backgroundColor: 'rgba(245, 158, 11, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'Signal & Telecom',
                        data: [40, 45, 42, 48, 52, 50, 45],
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.1)',
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { size: 11 } }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(51, 65, 85, 0.5)' },
                        ticks: { color: '#94a3b8' }
                    },
                    y: {
                        grid: { color: 'rgba(51, 65, 85, 0.5)' },
                        ticks: { color: '#94a3b8' },
                        beginAtZero: true
                    }
                }
            }
        });
    }

    // Department Chart
    const ctx2 = document.getElementById('deptChart');
    if (ctx2) {
        new Chart(ctx2, {
            type: 'doughnut',
            data: {
                labels: ['Engineering', 'Traction', 'Signal & Telecom'],
                datasets: [{
                    data: [112, 85, 50],
                    backgroundColor: ['#3b82f6', '#f59e0b', '#10b981'],
                    borderColor: '#1e293b',
                    borderWidth: 3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: { color: '#94a3b8', font: { size: 11 } }
                    }
                }
            }
        });
    }
}

// ============================================
// ACTIVITY LIST
// ============================================
function renderActivities() {
    const list = document.getElementById('activityList');
    if (!list) return;
    
    list.innerHTML = activities.map(a => `
        <div class="activity-item">
            <div class="activity-icon ${a.type}">
                <i class="fas ${a.icon}"></i>
            </div>
            <div class="activity-info">
                <div class="activity-text">${a.text}</div>
                <div class="activity-time">${a.time}</div>
            </div>
        </div>
    `).join('');
}

// ============================================
// CALENDAR
// ============================================
function renderCalendar() {
    const grid = document.getElementById('calendarGrid');
    if (!grid) return;
    
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const today = new Date();
    const startOfWeek = new Date(today);
    startOfWeek.setDate(today.getDate() - today.getDay() + 1);
    
    let html = days.map(d => `<div class="calendar-day-header">${d}</div>`).join('');
    
    for (let i = 0; i < 7; i++) {
        const date = new Date(startOfWeek);
        date.setDate(startOfWeek.getDate() + i);
        const isToday = date.toDateString() === today.toDateString();
        
        html += `
            <div class="calendar-day ${isToday ? 'today' : ''}">
                <div class="date">${date.getDate()}</div>
                ${renderDayBlocks(i)}
            </div>
        `;
    }
    
    grid.innerHTML = html;
}

function renderDayBlocks(dayIndex) {
    const allBlocks = [
        ...blockData.engineering.slice(0, 2),
        ...blockData.traction.slice(0, 1),
        ...blockData.signal.slice(0, 1)
    ];
    
    const dayBlocks = allBlocks.filter((_, i) => i % 3 === dayIndex % 3);
    
    return dayBlocks.map(b => {
        const dept = b.id.startsWith('ENG') ? 'engineering' : 
                     b.id.startsWith('TRD') ? 'traction' : 'signal';
        return `<div class="block-event ${dept}">${b.id}: ${b.route}</div>`;
    }).join('');
}

// ============================================
// CORRIDOR TABLE
// ============================================
function renderCorridors() {
    const tbody = document.getElementById('corridorTableBody');
    if (!tbody) return;
    
    tbody.innerHTML = corridorData.map(c => `
        <tr>
            <td><strong>${c.id}</strong></td>
            <td>${c.route}</td>
            <td>${c.length}</td>
            <td>${c.blocks}</td>
            <td>
                <div class="progress-bar" style="width: 100px; display: inline-block; vertical-align: middle;">
                    <div class="progress-fill engineering" style="width: ${parseInt(c.availability)}%"></div>
                </div>
                <span style="margin-left: 8px;">${c.availability}</span>
            </td>
            <td><span class="status-badge ${c.status}">${c.status.charAt(0).toUpperCase() + c.status.slice(1)}</span></td>
            <td><button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;">View</button></td>
        </tr>
    `).join('');
}

// ============================================
// DEFECTS
// ============================================
function renderDefects(filter = 'all') {
    const grid = document.getElementById('defectsGrid');
    if (!grid) return;
    
    const filtered = filter === 'all' ? defectsData : defectsData.filter(d => d.dept === filter);
    
    grid.innerHTML = filtered.map(d => `
        <div class="defect-card">
            <div class="defect-header">
                <span class="defect-id">${d.id}</span>
                <span class="priority-badge ${d.priority}">${d.priority}</span>
            </div>
            <div class="defect-title">${d.title}</div>
            <div class="defect-description">${d.desc}</div>
            <div class="defect-meta">
                <span><i class="fas fa-map-marker-alt"></i> ${d.location}</span>
                <span><i class="fas fa-calendar"></i> ${d.date}</span>
            </div>
        </div>
    `).join('');
}

// ============================================
// SLIDER VALUES
// ============================================
document.querySelectorAll('.slider').forEach(slider => {
    slider.addEventListener('input', (e) => {
        e.target.nextElementSibling.textContent = e.target.value + '%';
    });
});

// ============================================
// AI MODAL
// ============================================
document.getElementById('generatePlanBtn')?.addEventListener('click', () => {
    document.getElementById('modalOverlay').classList.add('active');
    simulateGeneration();
});

document.getElementById('modalClose')?.addEventListener('click', () => {
    document.getElementById('modalOverlay').classList.remove('active');
    resetGeneration();
});

document.getElementById('modalOverlay')?.addEventListener('click', (e) => {
    if (e.target === e.currentTarget) {
        document.getElementById('modalOverlay').classList.remove('active');
        resetGeneration();
    }
});

function simulateGeneration() {
    const steps = document.querySelectorAll('.progress-step');
    const progressBar = document.getElementById('progressBarAnimated');
    const statusText = document.querySelector('#generationStatus p');
    const messages = [
        'Integrating data from TMS, SMMS, TDMS, and COA...',
        'Running AI/ML optimization algorithms...',
        'Generating optimized block schedule...',
        'Block plan generated successfully!'
    ];
    
    let currentStep = 0;
    
    const interval = setInterval(() => {
        if (currentStep < steps.length) {
            steps.forEach(s => s.classList.remove('active'));
            steps[currentStep].classList.add('active');
            if (currentStep > 0) steps[currentStep - 1].classList.add('completed');
            statusText.textContent = messages[currentStep];
            progressBar.style.width = ((currentStep + 1) / steps.length * 100) + '%';
            currentStep++;
        } else {
            clearInterval(interval);
            setTimeout(() => {
                document.getElementById('modalOverlay').classList.remove('active');
                resetGeneration();
            }, 1500);
        }
    }, 1200);
}

function resetGeneration() {
    const steps = document.querySelectorAll('.progress-step');
    steps.forEach((s, i) => {
        s.classList.remove('active', 'completed');
        if (i === 0) s.classList.add('active');
    });
    document.getElementById('progressBarAnimated').style.width = '0%';
}

// ============================================
// AI OPTIMIZER
// ============================================
document.getElementById('runOptimizer')?.addEventListener('click', () => {
    const btn = document.getElementById('runOptimizer');
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Optimizing...';
    btn.disabled = true;
    
    setTimeout(() => {
        btn.innerHTML = '<i class="fas fa-check"></i> Optimization Complete';
        btn.style.background = 'var(--green)';
        
        // Update results with animation
        document.querySelectorAll('.result-bar').forEach(bar => {
            const target = bar.classList.contains('projected') ? '94' : 
                          bar.classList.contains('optimized') ? '89' : '62';
            bar.style.width = target + '%';
            bar.textContent = target + '%';
        });
        
        setTimeout(() => {
            btn.innerHTML = '<i class="fas fa-play"></i> Run AI Optimizer';
            btn.style.background = '';
            btn.disabled = false;
        }, 2000);
    }, 2000);
});

// ============================================
// DEFECT FILTER
// ============================================
document.getElementById('defectFilter')?.addEventListener('change', (e) => {
    renderDefects(e.target.value);
});

// ============================================
// WEEK/MONTH TOGGLE
// ============================================
document.querySelectorAll('.horizon-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.horizon-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderCalendar();
    });
});

// ============================================
// SIDEBAR TOGGLE
// ============================================
document.getElementById('sidebarToggle')?.addEventListener('click', () => {
    const sidebar = document.getElementById('sidebar');
    sidebar.classList.toggle('collapsed');
});

// ============================================
// INIT
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initCharts();
    renderActivities();
    renderCalendar();
    renderCorridors();
    renderDefects();
});
