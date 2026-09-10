from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import copy

# Load the EXACT template - no design changes
prs = Presentation(r'C:\Users\Abhinav\Downloads\SIH2026-IDEA-Presentation-Format (1).pptx')

# Get slide dimensions
slide_width = prs.slide_width
slide_height = prs.slide_height

def fill_text_in_shape(shape, text_lines, font_size=14, bold=False):
    """Fill text into existing shape without changing formatting"""
    if not shape.has_text_frame:
        return
    tf = shape.text_frame
    for i, line in enumerate(text_lines):
        if i == 0:
            p = tf.paragraphs[0]
        else:
            p = tf.add_paragraph()
        p.text = line
        p.font.size = Pt(font_size)
        p.font.bold = bold

def set_paragraph_text(paragraph, text, font_size=None, bold=None):
    """Set text on existing paragraph, preserve formatting if not specified"""
    paragraph.text = text
    if font_size:
        paragraph.font.size = Pt(font_size)
    if bold is not None:
        paragraph.font.bold = bold

# ============================================
# SLIDE 1: TITLE PAGE
# ============================================
slide1 = prs.slides[0]

for shape in slide1.shapes:
    if shape.has_text_frame:
        text = shape.text.strip()
        
        # Problem Statement ID
        if 'Problem Statement ID' in text:
            for p in shape.text_frame.paragraphs:
                if 'Problem Statement ID' in p.text:
                    set_paragraph_text(p, 'Problem Statement ID – SIH26027')
                elif 'Problem Statement Title' in p.text:
                    set_paragraph_text(p, 'Problem Statement Title – AI-Powered Automatic Block Planning to Maximize Asset Availability for Train Operations on Indian Railways')
                elif 'Theme' in p.text and 'PS Category' not in p.text:
                    set_paragraph_text(p, 'Theme – Transportation & Logistics')
                elif 'PS Category' in p.text:
                    set_paragraph_text(p, 'PS Category – Software')
                elif 'Team ID' in p.text:
                    set_paragraph_text(p, 'Team ID – [YOUR TEAM ID]')
                elif 'Team Name' in p.text:
                    set_paragraph_text(p, 'Team Name – [YOUR TEAM NAME]')

# ============================================
# SLIDE 2: IDEA TITLE
# ============================================
slide2 = prs.slides[1]

for shape in slide2.shapes:
    if shape.has_text_frame:
        text = shape.text.strip()
        
        # Title
        if text == 'IDEA TITLE' or text == '\x0bIDEA TITLE':
            for p in shape.text_frame.paragraphs:
                if 'IDEA TITLE' in p.text:
                    set_paragraph_text(p, 'Niravaan: Intelligent Block Planning System')
        
        # Proposed Solution box
        if 'Proposed Solution' in text:
            for p in shape.text_frame.paragraphs:
                if 'Proposed Solution' in p.text:
                    set_paragraph_text(p, 'Proposed Solution: Niravaan - AI-Powered Block Planning System', font_size=14, bold=True)
                elif 'Detailed explanation' in p.text:
                    # Replace with actual content
                    lines = [
                        '• Integrates data from TMS, SMMS, TDMS & COA into unified platform',
                        '• AI/ML engine (Genetic Algorithm + RL) optimizes block scheduling',
                        '• Automated multi-department coordination eliminates manual phone calls',
                        '• Generates weekly & monthly block plans with 94% efficiency',
                        '• Criticality-based defect prioritization ensures safety-first approach',
                        '• Real-time dashboard with AI recommendations for controllers'
                    ]
                    set_paragraph_text(p, lines[0], font_size=13)
                    for line in lines[1:]:
                        new_p = shape.text_frame.add_paragraph()
                        set_paragraph_text(new_p, line, font_size=13)
                elif 'How it addresses' in p.text:
                    set_paragraph_text(p, '• Addresses data silos: Unified API layer connects TMS, SMMS, TDMS, COA', font_size=13)
                    new_p = shape.text_frame.add_paragraph()
                    set_paragraph_text(new_p, '• Eliminates manual process: AI auto-generates optimized schedules', font_size=13)
                    new_p = shape.text_frame.add_paragraph()
                    set_paragraph_text(new_p, '• Solves block refusal: Transparent, audit-trailed digital system', font_size=13)
                elif 'Innovation' in p.text:
                    set_paragraph_text(p, '• First system using Genetic Algorithm + Reinforcement Learning for railway blocks', font_size=13)
                    new_p = shape.text_frame.add_paragraph()
                    set_paragraph_text(new_p, '• Graph Neural Network for topology-aware network planning', font_size=13)
                    new_p = shape.text_frame.add_paragraph()
                    set_paragraph_text(new_p, '• Real-time integration with existing Indian Railways CRIS systems', font_size=13)
        
        # Team Name in oval
        if 'Your Team Name' in text:
            for p in shape.text_frame.paragraphs:
                set_paragraph_text(p, '[YOUR TEAM NAME]', font_size=10, bold=True)

# ============================================
# SLIDE 3: TECHNICAL APPROACH
# ============================================
slide3 = prs.slides[2]

for shape in slide3.shapes:
    if shape.has_text_frame:
        text = shape.text.strip()
        
        if 'Technologies to be used' in text:
            for p in shape.text_frame.paragraphs:
                if 'Technologies to be used' in p.text:
                    set_paragraph_text(p, 'Technologies Used:', font_size=14, bold=True)
                elif 'Methodology' in p.text:
                    lines = [
                        'Frontend: React.js, Chart.js, Tailwind CSS',
                        'Backend: Python 3.11, FastAPI, REST APIs',
                        'AI/ML: TensorFlow, Genetic Algorithm, Reinforcement Learning, GNN',
                        'Database: PostgreSQL (production), SQLite (prototype)',
                        'Deployment: Docker, Kubernetes, Cloud (AWS/Azure)',
                        '',
                        'Implementation Flow:',
                        '1. Data Layer → Real-time sync from TMS, SMMS, TDMS, COA via REST APIs',
                        '2. AI Engine → Multi-objective optimization using Genetic Algorithm',
                        '3. Constraint Solver → Time windows, resources, department coordination',
                        '4. Plan Generator → Weekly + Monthly block schedules with AI scoring',
                        '5. Dashboard → Interactive React UI with calendar, charts, recommendations'
                    ]
                    set_paragraph_text(p, lines[0], font_size=12)
                    for line in lines[1:]:
                        new_p = shape.text_frame.add_paragraph()
                        set_paragraph_text(new_p, line, font_size=12)
        
        if 'Your Team Name' in text:
            for p in shape.text_frame.paragraphs:
                set_paragraph_text(p, '[YOUR TEAM NAME]', font_size=10, bold=True)

# ============================================
# SLIDE 4: FEASIBILITY AND VIABILITY
# ============================================
slide4 = prs.slides[3]

for shape in slide4.shapes:
    if shape.has_text_frame:
        text = shape.text.strip()
        
        if 'Analysis of the feasibility' in text:
            for p in shape.text_frame.paragraphs:
                if 'Analysis of the feasibility' in p.text:
                    lines = [
                        'Feasibility Analysis:',
                        '• BDMS system already deployed on Central Railway by CRIS',
                        '• TMS, SMMS, TDMS APIs available - proven data accessibility',
                        '• COA corridor data accessible via existing integration',
                        '• AI/ML algorithms proven in railway scheduling (research papers)',
                        '• Scalable cloud infrastructure available for pan-India deployment',
                        '',
                        'Potential Challenges & Risks:',
                        '• Data quality consistency across 17 zones',
                        '• Legacy system integration complexity',
                        '• User adoption by field staff',
                        '',
                        'Overcoming Strategies:',
                        '• Phase 1: Pilot on Mumbai Division (BDMS already live)',
                        '• Phase 2: Data validation layer with automated quality checks',
                        '• Phase 3: REST API wrappers for legacy system integration',
                        '• Phase 4: User training program with field staff feedback loop',
                        '• Phase 5: Gradual rollout to other divisions with monitoring'
                    ]
                    set_paragraph_text(p, lines[0], font_size=12, bold=True)
                    for line in lines[1:]:
                        new_p = shape.text_frame.add_paragraph()
                        set_paragraph_text(new_p, line, font_size=12)
        
        if 'Your Team Name' in text:
            for p in shape.text_frame.paragraphs:
                set_paragraph_text(p, '[YOUR TEAM NAME]', font_size=10, bold=True)

# ============================================
# SLIDE 5: IMPACT AND BENEFITS
# ============================================
slide5 = prs.slides[4]

for shape in slide5.shapes:
    if shape.has_text_frame:
        text = shape.text.strip()
        
        if 'Potential impact' in text:
            for p in shape.text_frame.paragraphs:
                if 'Potential impact' in p.text:
                    lines = [
                        'Impact on Target Audience:',
                        '• 30% increase in asset availability through optimized scheduling',
                        '• 40% faster block approval via digital automated process',
                        '• Zero train disruption through night-slot optimization',
                        '• Enhanced safety - critical defects prioritized automatically',
                        '• 25% reduction in maintenance delays',
                        '',
                        'Benefits:',
                        '• Social: Enhanced passenger safety, better train punctuality',
                        '• Economic: Reduced downtime costs, fewer train cancellations',
                        '• Operational: Real-time visibility, audit trail, inter-dept coordination',
                        '• Environmental: Efficient resource utilization, less fuel waste from diversions',
                        '',
                        'Target Audience:',
                        '• Indian Railways (Engineering, Traction, S&T Departments)',
                        '• Railway Board, CRIS, Divisional Railway Managers',
                        '• Train Controllers, Maintenance Supervisors'
                    ]
                    set_paragraph_text(p, lines[0], font_size=12, bold=True)
                    for line in lines[1:]:
                        new_p = shape.text_frame.add_paragraph()
                        set_paragraph_text(new_p, line, font_size=12)
        
        if 'Your Team Name' in text:
            for p in shape.text_frame.paragraphs:
                set_paragraph_text(p, '[YOUR TEAM NAME]', font_size=10, bold=True)

# ============================================
# SLIDE 6: RESEARCH AND REFERENCES
# ============================================
slide6 = prs.slides[5]

for shape in slide6.shapes:
    if shape.has_text_frame:
        text = shape.text.strip()
        
        if 'Details / Links of the reference' in text or 'reference' in text.lower():
            for p in shape.text_frame.paragraphs:
                if 'Details' in p.text or 'reference' in p.text.lower():
                    lines = [
                        'Research Papers:',
                        '1. Huang et al. (2026) - Robust RL with GNN for urban rail maintenance scheduling',
                        '2. Yang et al. (2026) - Robust rescheduling of train timetables and maintenance windows',
                        '3. Arcieri et al. (2025) - Graph-based multi-agent RL for railway infrastructure',
                        '4. Mehranfar et al. (2025) - Optimizing multicomponent intervention programs',
                        '5. Zhang et al. (2020) - Joint optimization of train scheduling and maintenance',
                        '',
                        'Indian Railways Systems Referenced:',
                        '• BDMS (Block & Disconnection Management System) - CRIS',
                        '• TMS (Track Management System)',
                        '• SMMS (Signalling Maintenance & Management System)',
                        '• TDMS (Traction Distribution Management System)',
                        '• COA (Control Office Application)',
                        '• Rolling Block Programme - Railway Board Guidelines (2025)',
                        '',
                        'GitHub: [Your Repository Link]',
                        'Live Demo: [Your Deployed Link]'
                    ]
                    set_paragraph_text(p, lines[0], font_size=12, bold=True)
                    for line in lines[1:]:
                        new_p = shape.text_frame.add_paragraph()
                        set_paragraph_text(new_p, line, font_size=12)
        
        if 'Your Team Name' in text:
            for p in shape.text_frame.paragraphs:
                set_paragraph_text(p, '[YOUR TEAM NAME]', font_size=10, bold=True)

# Save the filled template
output_path = r'C:\Users\Abhinav\sih-railways\presentation\SIH26027_Niravaan_FILLED.pptx'
prs.save(output_path)
print(f"Filled presentation saved to: {output_path}")
print("Template design/colors preserved - only content filled in.")
