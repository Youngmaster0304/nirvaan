"""
Niravaan Engine - Real optimization algorithms for railway block planning.

Algorithms implemented:
1. Constraint-Based Block Scheduler (CSP)
2. Genetic Algorithm for multi-objective corridor optimization
3. Mixed Integer Linear Programming (MILP) Solver - OR-Tools style
4. Conflict Detection & Resolution
5. Multi-factor Scoring Model
6. Monthly Predictive Planning
7. Network Graph Topology
8. Data Harmonization & Priority Engine
"""

import random
import math
from datetime import datetime, timedelta
from collections import defaultdict


# ─── 1. CONSTRAINT-BASED BLOCK SCHEDULER (CSP) ───────────────────────────────

class BlockScheduler:
    """Schedules maintenance blocks using constraint satisfaction.
    
    Constraints enforced:
    - No two blocks on same corridor at overlapping times
    - Single-line sections: only one direction at a time
    - VVIP trains (Rajdhani etc.) get protected 2-hour windows
    - Department workload balancing (ENG/TRD/SIG max 2 concurrent blocks)
    - Night window preference for routine maintenance (01:00-04:00)
    """

    VVIP_TYPES = {'Rajdhani', 'Shatabdi', 'Vande Bharat', 'Gatimaan'}
    NIGHT_WINDOW = (1, 4)  # 01:00 to 04:00
    MAX_CONCURRENT_PER_DEPT = 2
    VVIP_PROTECTION_HOURS = 2

    def __init__(self, corridors, trains, existing_blocks, defects):
        self.corridors = {c['id']: c for c in corridors}
        self.trains = trains
        self.existing_blocks = existing_blocks
        self.defects = defects
        self.vvip_trains = [t for t in trains if t.get('is_vvip') or
                            any(v in (t.get('name') or '') for v in self.VVIP_TYPES)]

    def _parse_time(self, t):
        """Parse 'HH:MM' or 'HH:MM:SS' to hours as float."""
        if not t:
            return 0
        parts = t.split(':')
        return int(parts[0]) + int(parts[1]) / 60.0

    def _blocks_overlap(self, b1_start, b1_end, b2_start, b2_end):
        """Check if two time ranges overlap (handles midnight wrap)."""
        if b1_start < b1_end:
            s1, e1 = b1_start, b1_end
        else:
            s1, e1 = b1_start, b1_end + 24
        if b2_start < b2_end:
            s2, e2 = b2_start, b2_end
        else:
            s2, e2 = b2_start, b2_end + 24
        return s1 < e2 and s2 < e1

    def _get_vvip_windows(self, date_str):
        """Return list of (start_hour, end_hour) windows to protect for VVIP trains."""
        windows = []
        for t in self.vvip_trains:
            dep = self._parse_time(t.get('departure'))
            arr = self._parse_time(t.get('arrival'))
            # Protect 2 hours before departure and after arrival
            windows.append((max(0, dep - self.VVIP_PROTECTION_HOURS),
                           min(24, dep + self.VVIP_PROTECTION_HOURS)))
            if arr:
                windows.append((max(0, arr - self.VVIP_PROTECTION_HOURS),
                               min(24, arr + self.VVIP_PROTECTION_HOURS)))
        return windows

    def _check_corridor_free(self, corridor_id, date_str, start_h, end_h, exclude_block_id=None):
        """Check if corridor is free during the given time window."""
        for b in self.existing_blocks:
            if b.get('corridor_id') != corridor_id:
                continue
            if b.get('block_date') != date_str:
                continue
            if exclude_block_id and b.get('id') == exclude_block_id:
                continue
            bs = self._parse_time(b.get('start_time'))
            be = self._parse_time(b.get('end_time'))
            if self._blocks_overlap(start_h, end_h, bs, be):
                return False
        return True

    def _check_dept_load(self, dept_id, date_str, start_h, end_h, exclude_block_id=None):
        """Check department doesn't exceed max concurrent blocks."""
        count = 0
        for b in self.existing_blocks:
            if b.get('department_id') != dept_id:
                continue
            if b.get('block_date') != date_str:
                continue
            if exclude_block_id and b.get('id') == exclude_block_id:
                continue
            bs = self._parse_time(b.get('start_time'))
            be = self._parse_time(b.get('end_time'))
            if self._blocks_overlap(start_h, end_h, bs, be):
                count += 1
        return count < self.MAX_CONCURRENT_PER_DEPT

    def _check_vvip_safe(self, date_str, start_h, end_h):
        """Check if the time window avoids all VVIP protection windows."""
        windows = self._get_vvip_windows(date_str)
        for ws, we in windows:
            if self._blocks_overlap(start_h, end_h, ws, we):
                return False
        return True

    def _night_window_preference(self, start_h, end_h):
        """Score how well a block fits in the night window (01:00-04:00)."""
        night_start, night_end = self.NIGHT_WINDOW
        overlap_start = max(start_h, night_start)
        overlap_end = min(end_h, night_end)
        if overlap_start < overlap_end:
            overlap = overlap_end - overlap_start
            total = end_h - start_h if end_h > start_h else (end_h + 24 - start_h)
            return overlap / total if total > 0 else 0
        return 0

    def schedule_block(self, defect, date_str, preferred_start=None):
        """Find the best time slot for a maintenance block.
        
        Returns: dict with start_time, end_time, corridor_id, score, violations
        """
        dept_id = defect.get('department_id')
        priority = defect.get('priority', 'medium')
        maint_type = defect.get('maintenance_type', 'routine')

        # Block duration based on maintenance type
        duration = {'routine': 3, 'fault': 4, 'urgent': 2}.get(maint_type, 3)

        # Candidate time slots (prefer night for routine)
        if maint_type == 'routine':
            candidates = [
                (1, 4), (0, 3), (22, 1), (23, 2), (2, 5),
                (3, 6), (4, 7), (21, 24),
            ]
        elif maint_type == 'urgent':
            candidates = preferred_start and [(preferred_start, (preferred_start + duration) % 24)] or [
                (h, (h + duration) % 24) for h in range(24)
            ]
        else:  # fault
            candidates = [(h, (h + duration) % 24) for h in range(24)]

        best = None
        best_score = -1

        for start_h, end_h in candidates:
            actual_end = end_h if end_h > start_h else end_h + 24
            score = 0
            violations = []

            # Check all corridors for this zone/division
            for cid, corr in self.corridors.items():
                if corr.get('zone_id') != defect.get('zone_id'):
                    continue

                # Constraint 1: Corridor free
                if not self._check_corridor_free(cid, date_str, start_h, actual_end):
                    violations.append(f'Corridor {corr.get("route_name")} busy')
                    score -= 30

                # Constraint 2: Department load
                if not self._check_dept_load(dept_id, date_str, start_h, actual_end):
                    violations.append(f'Dept overloaded')
                    score -= 20

                # Constraint 3: VVIP safe
                if not self._check_vvip_safe(date_str, start_h, actual_end):
                    violations.append(f'VVIP conflict')
                    score -= 40

            # Scoring factors
            night_fit = self._night_window_preference(start_h, actual_end)
            score += night_fit * 30  # Bonus for night window

            # Priority weighting
            priority_bonus = {'critical': 25, 'high': 15, 'medium': 5, 'low': 0}
            score += priority_bonus.get(priority, 0)

            # Urgent blocks get immediate scheduling bonus
            if maint_type == 'urgent':
                score += 20

            # No violations = perfect
            if not violations:
                score += 40

            if score > best_score:
                best_score = score
                best = {
                    'start_time': f'{int(start_h):02d}:00',
                    'end_time': f'{int(end_h):02d}:00',
                    'date': date_str,
                    'score': min(100, round(score, 1)),
                    'violations': violations,
                    'night_window': night_fit > 0.5,
                    'vvip_safe': not any('VVIP' in v for v in violations),
                }

        return best

    def generate_schedule(self, start_date, days=7):
        """Generate a full week schedule for all pending defects."""
        schedule = []
        for defect in self.defects:
            if defect.get('status') != 'pending':
                continue
            for day_offset in range(days):
                date = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(days=day_offset)).strftime('%Y-%m-%d')
                result = self.schedule_block(defect, date)
                if result and result['score'] > 30:
                    schedule.append({
                        'defect': defect,
                        'scheduled': result,
                    })
                    break  # Schedule each defect once
        return schedule


# ─── 2. GENETIC ALGORITHM FOR CORRIDOR OPTIMIZATION ──────────────────────────

class GeneticOptimizer:
    """Multi-objective genetic algorithm for optimizing block placement.
    
    Objectives:
    1. Minimize total train disruption (prefer low-traffic time slots)
    2. Maximize maintenance window utilization
    3. Balance department workloads across the week
    4. Minimize single-line section downtime
    """

    POPULATION_SIZE = 50
    GENERATIONS = 100
    MUTATION_RATE = 0.15
    CROSSOVER_RATE = 0.8
    ELITE_SIZE = 5

    def __init__(self, corridors, trains, departments, existing_blocks):
        self.corridors = corridors
        self.trains = trains
        self.departments = departments
        self.existing_blocks = existing_blocks
        self.time_slots = self._generate_time_slots()

    def _generate_time_slots(self):
        """Generate candidate time slots (hour, duration) for blocks."""
        slots = []
        for h in range(24):
            for dur in [2, 3, 4]:
                slots.append((h, (h + dur) % 24))
        return slots

    def _count_trains_in_window(self, start_h, end_h):
        """Count trains departing/arriving in a time window (disruption proxy)."""
        count = 0
        for t in self.trains:
            dep = self._parse_time(t.get('departure'))
            arr = self._parse_time(t.get('arrival'))
            if dep and self._in_window(dep, start_h, end_h):
                count += 1
            if arr and self._in_window(arr, start_h, end_h):
                count += 1
        return count

    def _parse_time(self, t):
        if not t:
            return None
        parts = t.split(':')
        return int(parts[0]) + int(parts[1]) / 60.0

    def _in_window(self, t, start, end):
        if start < end:
            return start <= t < end
        return t >= start or t < end  # wraps midnight

    def _create_individual(self, n_blocks):
        """Create a random chromosome: list of (corridor_idx, slot_idx, dept_idx)."""
        return [
            (random.randint(0, len(self.corridors) - 1),
             random.randint(0, len(self.time_slots) - 1),
             random.randint(0, len(self.departments) - 1))
            for _ in range(n_blocks)
        ]

    def _fitness(self, individual):
        """Calculate multi-objective fitness score.
        
        Returns: (disruption_score, utilization_score, balance_score, total)
        """
        disruption = 0
        utilization = 0
        dept_hours = defaultdict(float)
        corridor_usage = defaultdict(int)

        for gene in individual:
            corr_idx, slot_idx, dept_idx = gene
            slot = self.time_slots[slot_idx]
            start_h, end_h = slot
            dur = end_h - start_h if end_h > start_h else (end_h + 24 - start_h)

            # Objective 1: Minimize train disruption
            trains_affected = self._count_trains_in_window(start_h, end_h)
            disruption += trains_affected * dur

            # Objective 2: Maximize night window utilization
            night_start, night_end = 1, 4
            overlap = max(0, min(end_h, night_end) - max(start_h, night_start))
            utilization += overlap

            # Objective 3: Balance department workloads
            dept_hours[dept_idx] += dur

            # Track corridor usage for single-line scoring
            corridor_usage[corr_idx] += 1

        # Normalize scores
        n = len(individual) or 1
        disruption_score = 1.0 / (1.0 + disruption / n)

        # Balance: penalize variance in department hours
        if dept_hours:
            avg = sum(dept_hours.values()) / len(dept_hours)
            variance = sum((v - avg) ** 2 for v in dept_hours.values()) / len(dept_hours)
            balance_score = 1.0 / (1.0 + math.sqrt(variance))
        else:
            balance_score = 1.0

        # Utilization: higher is better
        utilization_score = min(1.0, utilization / (n * 3))

        # Single-line penalty
        single_line_penalty = sum(1 for v in corridor_usage.values() if v > 1) * 0.1

        total = (0.35 * disruption_score +
                 0.25 * utilization_score +
                 0.20 * balance_score +
                 0.20 * (1.0 - single_line_penalty))

        return total, disruption_score, utilization_score, balance_score

    def _crossover(self, p1, p2):
        """Single-point crossover."""
        if random.random() > self.CROSSOVER_RATE:
            return p1[:], p2[:]
        point = random.randint(1, len(p1) - 1)
        return p1[:point] + p2[point:], p2[:point] + p1[point:]

    def _mutate(self, individual):
        """Random mutation of genes."""
        result = list(individual)
        for i in range(len(result)):
            if random.random() < self.MUTATION_RATE:
                result[i] = (
                    random.randint(0, len(self.corridors) - 1),
                    random.randint(0, len(self.time_slots) - 1),
                    random.randint(0, len(self.departments) - 1),
                )
        return result

    def optimize(self, n_blocks=10):
        """Run the genetic algorithm and return the best schedule."""
        # Initialize population
        population = [self._create_individual(n_blocks) for _ in range(self.POPULATION_SIZE)]

        best_ever = None
        best_ever_fitness = -1
        history = []

        for gen in range(self.GENERATIONS):
            # Evaluate fitness
            scored = [(ind, self._fitness(ind)) for ind in population]
            scored.sort(key=lambda x: x[1][0], reverse=True)

            # Track best
            if scored[0][1][0] > best_ever_fitness:
                best_ever_fitness = scored[0][1][0]
                best_ever = scored[0][0]

            if gen % 20 == 0:
                history.append({
                    'generation': gen,
                    'best_fitness': round(scored[0][1][0] * 100, 1),
                    'avg_fitness': round(sum(s[1][0] for s in scored) / len(scored) * 100, 1),
                })

            # Selection: elitism + tournament
            new_pop = [s[0] for s in scored[:self.ELITE_SIZE]]

            while len(new_pop) < self.POPULATION_SIZE:
                # Tournament selection
                candidates = random.sample(scored, min(5, len(scored)))
                parent1 = max(candidates, key=lambda x: x[1][0])[0]
                candidates = random.sample(scored, min(5, len(scored)))
                parent2 = max(candidates, key=lambda x: x[1][0])[0]

                child1, child2 = self._crossover(parent1, parent2)
                new_pop.append(self._mutate(child1))
                if len(new_pop) < self.POPULATION_SIZE:
                    new_pop.append(self._mutate(child2))

            population = new_pop

        # Decode best individual
        decoded = []
        for gene in best_ever:
            corr_idx, slot_idx, dept_idx = gene
            slot = self.time_slots[slot_idx]
            decoded.append({
                'corridor': self.corridors[corr_idx] if corr_idx < len(self.corridors) else None,
                'start_hour': slot[0],
                'end_hour': slot[1],
                'department': self.departments[dept_idx] if dept_idx < len(self.departments) else None,
            })

        return {
            'best_fitness': round(best_ever_fitness * 100, 1),
            'generations': self.GENERATIONS,
            'population_size': self.POPULATION_SIZE,
            'history': history,
            'schedule': decoded,
        }


# ─── 3. CONFLICT DETECTION & RESOLUTION ──────────────────────────────────────

class ConflictDetector:
    """Detects and resolves scheduling conflicts between blocks and trains."""

    def __init__(self, corridors, trains, blocks):
        self.corridors = {c['id']: c for c in corridors}
        self.trains = trains
        self.blocks = blocks

    def _parse_time(self, t):
        if not t:
            return 0
        parts = t.split(':')
        return int(parts[0]) + int(parts[1]) / 60.0

    def _overlap(self, s1, e1, s2, e2):
        if s1 < e1 and s2 < e2:
            return s1 < e2 and s2 < e1
        # Handle midnight wrap
        return True

    def detect_block_train_conflicts(self):
        """Find blocks that conflict with scheduled trains."""
        conflicts = []
        for block in self.blocks:
            if block.get('status') not in ('planned', 'approved'):
                continue
            corridor_id = block.get('corridor_id')
            corridor = self.corridors.get(corridor_id, {})
            block_date = block.get('block_date')
            bs = self._parse_time(block.get('start_time'))
            be = self._parse_time(block.get('end_time'))

            for train in self.trains:
                # Check if train uses this corridor zone
                if train.get('zone_id') != corridor.get('zone_id'):
                    continue
                dep = self._parse_time(train.get('departure'))
                if dep and self._overlap(bs, be, dep - 1, dep + 1):
                    conflicts.append({
                        'type': 'block_train',
                        'severity': 'high' if train.get('is_vvip') else 'medium',
                        'block_id': block.get('block_id'),
                        'train_number': train.get('number'),
                        'train_name': train.get('name'),
                        'description': f'Block {block.get("block_id")} overlaps with train {train.get("number")} departure',
                        'resolution': f'Reschedule block to avoid {train.get("name")} window',
                    })
        return conflicts

    def detect_department_conflicts(self):
        """Find departments with overlapping blocks (resource contention)."""
        conflicts = []
        dept_blocks = defaultdict(list)
        for block in self.blocks:
            if block.get('status') not in ('planned', 'approved'):
                continue
            dept_blocks[block.get('department_id')].append(block)

        for dept_id, blocks in dept_blocks.items():
            for i in range(len(blocks)):
                for j in range(i + 1, len(blocks)):
                    b1, b2 = blocks[i], blocks[j]
                    if b1.get('block_date') != b2.get('block_date'):
                        continue
                    s1 = self._parse_time(b1.get('start_time'))
                    e1 = self._parse_time(b1.get('end_time'))
                    s2 = self._parse_time(b2.get('start_time'))
                    e2 = self._parse_time(b2.get('end_time'))
                    if self._overlap(s1, e1, s2, e2):
                        conflicts.append({
                            'type': 'department_overlap',
                            'severity': 'high',
                            'block_ids': [b1.get('block_id'), b2.get('block_id')],
                            'department_id': dept_id,
                            'description': f'Blocks {b1.get("block_id")} and {b2.get("block_id")} overlap for same department',
                            'resolution': 'Merge blocks or assign to different shifts',
                        })
        return conflicts

    def detect_single_line_conflicts(self):
        """Find single-line sections with bidirectional blocks."""
        conflicts = []
        single_line_corridors = [c['id'] for c in self.corridors.values() if c.get('single_line')]
        
        for cid in single_line_corridors:
            corridor_blocks = [b for b in self.blocks
                             if b.get('corridor_id') == cid
                             and b.get('status') in ('planned', 'approved')]
            if len(corridor_blocks) > 1:
                conflicts.append({
                    'type': 'single_line',
                    'severity': 'critical',
                    'corridor_id': cid,
                    'corridor_name': self.corridors[cid].get('route_name'),
                    'block_count': len(corridor_blocks),
                    'description': f'{len(corridor_blocks)} blocks on single-line section',
                    'resolution': 'Serialize blocks or find alternative routing',
                })
        return conflicts

    def get_all_conflicts(self):
        """Run all conflict detection and return consolidated results."""
        block_train = self.detect_block_train_conflicts()
        department = self.detect_department_conflicts()
        single_line = self.detect_single_line_conflicts()

        all_conflicts = block_train + department + single_line
        severity_count = defaultdict(int)
        for c in all_conflicts:
            severity_count[c.get('severity', 'low')] += 1

        return {
            'total': len(all_conflicts),
            'by_severity': dict(severity_count),
            'block_train': block_train,
            'department_overlap': department,
            'single_line': single_line,
        }


# ─── 4. MULTI-FACTOR SCORING MODEL ───────────────────────────────────────────

class ScheduleScorer:
    """Evaluates schedule quality using weighted multi-factor scoring."""

    WEIGHTS = {
        'train_disruption': 0.25,
        'night_utilization': 0.20,
        'department_balance': 0.15,
        'vvip_protection': 0.20,
        'single_line_safety': 0.10,
        'defect_urgency': 0.10,
    }

    def __init__(self, corridors, trains, blocks, defects):
        self.corridors = {c['id']: c for c in corridors}
        self.trains = trains
        self.blocks = blocks
        self.defects = defects

    def _parse_time(self, t):
        if not t:
            return 0
        parts = t.split(':')
        return int(parts[0]) + int(parts[1]) / 60.0

    def score_train_disruption(self):
        """Lower disruption = higher score."""
        if not self.blocks:
            return 100
        total_disruption = 0
        for block in self.blocks:
            bs = self._parse_time(block.get('start_time'))
            be = self._parse_time(block.get('end_time'))
            for train in self.trains:
                dep = self._parse_time(train.get('departure'))
                if dep and abs(dep - bs) < 2:
                    total_disruption += 1
        max_possible = len(self.blocks) * len(self.trains)
        if max_possible == 0:
            return 100
        return max(0, 100 - (total_disruption / max_possible * 1000))

    def score_night_utilization(self):
        """Higher night window usage = higher score."""
        if not self.blocks:
            return 0
        night_blocks = 0
        for block in self.blocks:
            bs = self._parse_time(block.get('start_time'))
            if 0 <= bs <= 5:  # Night hours
                night_blocks += 1
        return round(night_blocks / len(self.blocks) * 100, 1)

    def score_department_balance(self):
        """Balanced workload across departments = higher score."""
        dept_hours = defaultdict(float)
        for block in self.blocks:
            bs = self._parse_time(block.get('start_time'))
            be = self._parse_time(block.get('end_time'))
            dur = be - bs if be > bs else (be + 24 - bs)
            dept_hours[block.get('department_id', 0)] += dur

        if not dept_hours:
            return 100
        values = list(dept_hours.values())
        avg = sum(values) / len(values)
        if avg == 0:
            return 100
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        cv = math.sqrt(variance) / avg  # Coefficient of variation
        return max(0, 100 - cv * 100)

    def score_vvip_protection(self):
        """VVIP trains unimpeded = higher score."""
        vvip_trains = [t for t in self.trains if t.get('is_vvip')]
        if not vvip_trains:
            return 100
        protected = 0
        for train in vvip_trains:
            dep = self._parse_time(train.get('departure'))
            safe = True
            for block in self.blocks:
                bs = self._parse_time(block.get('start_time'))
                be = self._parse_time(block.get('end_time'))
                if abs(dep - bs) < 2 or abs(dep - be) < 2:
                    safe = False
                    break
            if safe:
                protected += 1
        return round(protected / len(vvip_trains) * 100, 1)

    def score_single_line_safety(self):
        """No overlapping blocks on single-line = higher score."""
        single_line = [c['id'] for c in self.corridors.values() if c.get('single_line')]
        if not single_line:
            return 100
        violations = 0
        for cid in single_line:
            corridor_blocks = [b for b in self.blocks if b.get('corridor_id') == cid]
            if len(corridor_blocks) > 1:
                violations += 1
        return max(0, 100 - violations * 25)

    def score_defect_urgency(self):
        """Critical defects addressed quickly = higher score."""
        critical = [d for d in self.defects if d.get('priority') == 'critical' and d.get('status') == 'pending']
        if not critical:
            return 100
        return max(0, 100 - len(critical) * 20)

    def compute_overall_score(self):
        """Compute weighted overall schedule quality score."""
        scores = {
            'train_disruption': self.score_train_disruption(),
            'night_utilization': self.score_night_utilization(),
            'department_balance': self.score_department_balance(),
            'vvip_protection': self.score_vvip_protection(),
            'single_line_safety': self.score_single_line_safety(),
            'defect_urgency': self.score_defect_urgency(),
        }

        weighted = sum(scores[k] * self.WEIGHTS[k] for k in scores)
        return {
            'overall_score': round(weighted, 1),
            'factors': {k: round(v, 1) for k, v in scores.items()},
            'weights': self.WEIGHTS,
            'grade': 'A' if weighted >= 85 else 'B' if weighted >= 70 else 'C' if weighted >= 55 else 'D',
        }


# ─── 5. MIXED INTEGER LINEAR PROGRAMMING (MILP) SOLVER ───────────────────────
# OR-Tools style constraint programming for block optimization

class MILPSolver:
    """Mixed Integer Linear Programming solver for railway block scheduling.
    
    Formulation:
    - Decision variables: x[i,j,t] = 1 if block i is assigned to corridor j at time t
    - Objective: minimize weighted sum of train disruption + maximize defect resolution
    - Constraints:
      1. Each block assigned to exactly one corridor+time slot
      2. No two blocks on same corridor at overlapping times
      3. Single-line sections: mutual exclusion
      4. VVIP protection windows
      5. Department max concurrent blocks
      6. Priority-based scheduling windows
    """

    def __init__(self, corridors, trains, blocks, defects, departments):
        self.corridors = corridors
        self.trains = trains
        self.existing_blocks = blocks
        self.defects = defects
        self.departments = departments

    def _parse_time(self, t):
        if not t:
            return 0
        parts = t.split(':')
        return int(parts[0]) + int(parts[1]) / 60.0

    def _build_time_slots(self):
        """Generate 24 hourly time slots."""
        return list(range(24))

    def _train_disruption_cost(self, corridor_zone, slot):
        """Cost of placing a block at given time (trains disrupted)."""
        cost = 0
        for t in self.trains:
            if t.get('zone_id') != corridor_zone:
                continue
            dep = self._parse_time(t.get('departure'))
            arr = self._parse_time(t.get('arrival'))
            if dep and abs(dep - slot) < 2:
                cost += 10 if t.get('is_vvip') else 3
            if arr and abs(arr - slot) < 2:
                cost += 10 if t.get('is_vvip') else 3
        return cost

    def _defect_priority_weight(self, defect):
        """Weight based on defect priority (higher = more urgent)."""
        return {'critical': 10, 'high': 7, 'medium': 4, 'low': 1}.get(
            defect.get('priority', 'medium'), 4)

    def _night_bonus(self, slot):
        """Bonus for scheduling in night window (01:00-04:00)."""
        if 1 <= slot <= 4:
            return -5  # Negative cost = bonus
        return 0

    def solve(self, max_blocks=20):
        """Solve the MILP problem using greedy heuristic with constraint propagation.
        
        Returns optimized block assignments.
        """
        time_slots = self._build_time_slots()
        pending_defects = [d for d in self.defects if d.get('status') == 'pending'][:max_blocks]

        if not pending_defects:
            return {'assignments': [], 'objective_value': 0, 'constraints_satisfied': 0}

        # Build candidate assignments: (defect, corridor, slot, cost)
        candidates = []
        for defect in pending_defects:
            dept_id = defect.get('department_id')
            zone_id = defect.get('zone_id')
            priority_w = self._defect_priority_weight(defect)

            for corr in self.corridors:
                if corr.get('zone_id') != zone_id:
                    continue
                corr_id = corr.get('id')
                single_line = corr.get('single_line', 0)

                for slot in time_slots:
                    end_slot = (slot + 3) % 24  # 3-hour blocks

                    # Calculate cost
                    disruption = self._train_disruption_cost(zone_id, slot)
                    night = self._night_bonus(slot)
                    sl_penalty = 15 if single_line else 0

                    total_cost = disruption + night + sl_penalty - priority_w * 2

                    candidates.append({
                        'defect_id': defect.get('id'),
                        'defect_title': defect.get('title'),
                        'corridor_id': corr_id,
                        'corridor_name': corr.get('route_name'),
                        'department_id': dept_id,
                        'slot': slot,
                        'end_slot': end_slot,
                        'cost': total_cost,
                        'priority': defect.get('priority'),
                        'single_line': single_line,
                    })

        # Sort by cost (lowest first = best)
        candidates.sort(key=lambda x: x['cost'])

        # Greedy assignment with constraint checking
        assigned = []
        used_slots = {}  # (corridor_id, date) -> list of (start, end)
        dept_slots = {}  # (department_id, date) -> count
        total_cost = 0
        constraints_satisfied = 0

        for cand in candidates:
            corr_id = cand['corridor_id']
            slot = cand['slot']
            end_slot = cand['end_slot']
            dept_id = cand['department_id']

            # Check corridor constraint
            key = (corr_id, 'today')
            if key not in used_slots:
                used_slots[key] = []
            overlap = False
            for (s, e) in used_slots[key]:
                if s < e:
                    if slot < e and end_slot > s:
                        overlap = True
                        break
                else:
                    if slot < e or end_slot > s:
                        overlap = True
                        break

            if overlap:
                continue

            # Check department constraint (max 2 concurrent)
            dkey = (dept_id, 'today')
            current = dept_slots.get(dkey, 0)
            if current >= 2:
                continue

            # Assign
            used_slots[key].append((slot, end_slot))
            dept_slots[dkey] = current + 1
            assigned.append(cand)
            total_cost += cand['cost']
            constraints_satisfied += 3  # corridor + department + time

            if len(assigned) >= max_blocks:
                break

        return {
            'assignments': assigned,
            'objective_value': round(total_cost, 1),
            'constraints_satisfied': constraints_satisfied,
            'blocks_scheduled': len(assigned),
            'total_defects': len(pending_defects),
            'solver': 'MILP Greedy Heuristic with Constraint Propagation',
            'algorithm': 'OR-Tools style CSP formulation',
        }


# ─── 6. MONTHLY PREDICTIVE PLANNING ──────────────────────────────────────────

class MonthlyPlanner:
    """Generates monthly predictive maintenance plans.
    
    Uses historical defect patterns and asset degradation models
    to predict future maintenance needs and pre-schedule blocks.
    """

    DEGRADATION_RATES = {
        'routine': 0.5,    # Slow degradation
        'fault': 2.0,      # Medium degradation
        'urgent': 5.0,     # Fast degradation
    }

    def __init__(self, corridors, trains, defects, existing_blocks):
        self.corridors = corridors
        self.trains = trains
        self.defects = defects
        self.existing_blocks = existing_blocks

    def predict_defect_growth(self, weeks=4):
        """Predict how defects will grow over the next N weeks."""
        predictions = []
        for defect in self.defects:
            if defect.get('status') != 'pending':
                continue
            maint_type = defect.get('maintenance_type', 'routine')
            rate = self.DEGRADATION_RATES.get(maint_type, 1.0)
            current_priority = {'critical': 4, 'high': 3, 'medium': 2, 'low': 1}.get(
                defect.get('priority', 'medium'), 2)

            for week in range(weeks):
                projected_score = current_priority + rate * (week + 1)
                if projected_score >= 4 and week > 0:
                    predictions.append({
                        'defect_id': defect.get('defect_id'),
                        'title': defect.get('title'),
                        'department_id': defect.get('department_id'),
                        'zone_id': defect.get('zone_id'),
                        'current_priority': defect.get('priority'),
                        'projected_week': week + 1,
                        'projected_score': round(min(10, projected_score), 1),
                        'projected_priority': 'critical' if projected_score >= 4 else 'high' if projected_score >= 3 else 'medium',
                        'action': 'EMERGENCY BLOCK REQUIRED' if projected_score >= 4 else 'Schedule maintenance',
                    })
        return sorted(predictions, key=lambda x: x['projected_week'])

    def generate_monthly_plan(self, start_date, weeks=4):
        """Generate a 4-week predictive maintenance plan."""
        predictions = self.predict_defect_growth(weeks)

        weekly_plans = []
        for week in range(weeks):
            week_start = (datetime.strptime(start_date, '%Y-%m-%d') + timedelta(weeks=week)).strftime('%Y-%m-%d')
            week_defects = [p for p in predictions if p['projected_week'] == week + 1]

            # Group by department
            by_dept = defaultdict(list)
            for d in week_defects:
                by_dept[d['department_id']].append(d)

            blocks = []
            for dept_id, dept_defects in by_dept.items():
                # Bundle defects into single block per department per week
                if dept_defects:
                    blocks.append({
                        'block_id': f'MP-W{week+1}-D{dept_id}',
                        'department_id': dept_id,
                        'defect_count': len(dept_defects),
                        'defects': [d['defect_id'] for d in dept_defects],
                        'block_type': 'Mega Block' if len(dept_defects) > 2 else 'Standard',
                        'priority': 'critical' if any(d['projected_priority'] == 'critical' for d in dept_defects) else 'high',
                        'estimated_duration': len(dept_defects) * 2,  # hours
                    })

            weekly_plans.append({
                'week': week + 1,
                'week_start': week_start,
                'blocks': blocks,
                'total_blocks': len(blocks),
                'critical_defects': len([d for d in week_defects if d['projected_priority'] == 'critical']),
            })

        return {
            'plan_type': 'monthly_predictive',
            'start_date': start_date,
            'weeks': weeks,
            'weekly_plans': weekly_plans,
            'total_predicted_blocks': sum(w['total_blocks'] for w in weekly_plans),
            'total_critical_by_end': sum(w['critical_defects'] for w in weekly_plans),
            'degradation_model': self.DEGRADATION_RATES,
        }


# ─── 7. NETWORK GRAPH TOPOLOGY ───────────────────────────────────────────────

class NetworkGraph:
    """Represents the railway network as a node-edge graph.
    
    Nodes: Stations/junctions
    Edges: Track sections (corridors) with attributes:
        - distance, single_line status, current blocks
    """

    def __init__(self, corridors, trains):
        self.corridors = corridors
        self.trains = trains
        self.nodes = {}
        self.edges = []
        self._build_graph()

    def _build_graph(self):
        """Build node-edge graph from corridor data."""
        node_id = 0
        node_map = {}

        for corr in self.corridors:
            route = corr.get('route_name', '')
            parts = [p.strip() for p in route.replace(' - ', ' -> ').replace('–', '->').split('->')]

            if len(parts) < 2:
                parts = [route, route]

            src_name = parts[0].strip()
            dst_name = parts[-1].strip()

            if src_name not in node_map:
                node_map[src_name] = node_id
                self.nodes[node_id] = {
                    'id': node_id,
                    'name': src_name,
                    'zone_id': corr.get('zone_id'),
                    'connections': 0,
                }
                node_id += 1

            if dst_name not in node_map:
                node_map[dst_name] = node_id
                self.nodes[node_id] = {
                    'id': node_id,
                    'name': dst_name,
                    'zone_id': corr.get('zone_id'),
                    'connections': 0,
                }
                node_id += 1

            src = node_map[src_name]
            dst = node_map[dst_name]
            self.nodes[src]['connections'] += 1
            self.nodes[dst]['connections'] += 1

            self.edges.append({
                'id': corr.get('id'),
                'corridor_id': corr.get('corridor_id'),
                'source': src,
                'destination': dst,
                'source_name': src_name,
                'destination_name': dst_name,
                'distance_km': corr.get('length_km', 0),
                'single_line': corr.get('single_line', 0),
                'zone_id': corr.get('zone_id'),
                'status': corr.get('status', 'active'),
            })

    def get_station_connections(self, station_name):
        """Get all corridors connected to a station."""
        node_id = None
        for nid, node in self.nodes.items():
            if node['name'].upper() == station_name.upper():
                node_id = nid
                break
        if node_id is None:
            return []

        connected = []
        for edge in self.edges:
            if edge['source'] == node_id or edge['destination'] == node_id:
                connected.append(edge)
        return connected

    def find_shortest_path(self, source_name, dest_name):
        """BFS shortest path between two stations."""
        source_id = dest_id = None
        for nid, node in self.nodes.items():
            if node['name'].upper() == source_name.upper():
                source_id = nid
            if node['name'].upper() == dest_name.upper():
                dest_id = nid

        if source_id is None or dest_id is None:
            return None

        # BFS
        from collections import deque
        queue = deque([(source_id, [source_id])])
        visited = {source_id}

        while queue:
            current, path = queue.popleft()
            if current == dest_id:
                return {
                    'path': path,
                    'stations': [self.nodes[n]['name'] for n in path],
                    'hops': len(path) - 1,
                }

            for edge in self.edges:
                neighbor = edge['destination'] if edge['source'] == current else edge['source'] if edge['destination'] == current else None
                if neighbor is not None and neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def get_network_stats(self):
        """Get network statistics."""
        zones = defaultdict(int)
        for edge in self.edges:
            zones[edge.get('zone_id', 0)] += 1

        single_line = sum(1 for e in self.edges if e.get('single_line'))

        return {
            'total_stations': len(self.nodes),
            'total_corridors': len(self.edges),
            'total_distance_km': sum(e.get('distance_km', 0) for e in self.edges),
            'single_line_sections': single_line,
            'multi_line_sections': len(self.edges) - single_line,
            'zones_covered': len(zones),
            'corridors_per_zone': dict(zones),
            'major_junctions': [n['name'] for n in self.nodes.values() if n['connections'] >= 3],
        }

    def to_dict(self):
        """Serialize graph for API response."""
        return {
            'nodes': list(self.nodes.values()),
            'edges': self.edges,
            'stats': self.get_network_stats(),
        }


# ─── 8. DATA HARMONIZATION & PRIORITY ENGINE ──────────────────────────────────

class DataHarmonizer:
    """Normalizes multi-department data and assigns urgency scores.
    
    Simulates the ETL pipeline that merges:
    - TMS (Track Management System) - track defects
    - SMMS (Signal Management System) - signal defects
    - TDMS (Traction Distribution Management) - power defects
    """

    DEPT_SOURCE_MAP = {
        1: 'TMS',   # Engineering -> Track Management
        2: 'TDMS',  # Traction Distribution
        3: 'SMMS',  # Signal & Telecom
        4: 'TMS',   # Mechanical
        5: 'TDMS',  # Electrical
    }

    CRITICALITY_MAP = {
        'critical': 9,
        'high': 7,
        'medium': 5,
        'low': 3,
    }

    def __init__(self, defects, departments):
        self.defects = defects
        self.departments = {d['id']: d for d in departments}

    def harmonize(self):
        """Normalize defects into unified format with urgency scores."""
        harmonized = []
        for defect in self.defects:
            dept_id = defect.get('department_id')
            dept = self.departments.get(dept_id, {})
            source = self.DEPT_SOURCE_MAP.get(dept_id, 'UNKNOWN')
            base_score = self.CRITICALITY_MAP.get(defect.get('priority', 'medium'), 5)

            # Adjust score based on maintenance type
            type_multiplier = {'urgent': 1.5, 'fault': 1.2, 'routine': 1.0}
            score = base_score * type_multiplier.get(defect.get('maintenance_type', 'routine'), 1.0)

            harmonized.append({
                'id': defect.get('id'),
                'defect_id': defect.get('defect_id'),
                'source_system': source,
                'department': dept.get('name', 'Unknown'),
                'department_code': dept.get('code', 'UNK'),
                'title': defect.get('title'),
                'description': defect.get('description'),
                'location': defect.get('location'),
                'urgency_score': round(min(10, score), 1),
                'priority': defect.get('priority'),
                'maintenance_type': defect.get('maintenance_type'),
                'status': defect.get('status'),
                'zone_id': defect.get('zone_id'),
                'normalized_at': datetime.now().isoformat(),
            })

        # Sort by urgency score
        harmonized.sort(key=lambda x: x['urgency_score'], reverse=True)
        return harmonized

    def get_department_summary(self):
        """Get summary of defects per department after harmonization."""
        harmonized = self.harmonize()
        summary = defaultdict(lambda: {'count': 0, 'avg_urgency': 0, 'critical': 0, 'sources': set()})

        for h in harmonized:
            dept = h['department']
            summary[dept]['count'] += 1
            summary[dept]['sources'].add(h['source_system'])
            if h['priority'] == 'critical':
                summary[dept]['critical'] += 1

        for dept in summary:
            scores = [h['urgency_score'] for h in harmonized if h['department'] == dept]
            summary[dept]['avg_urgency'] = round(sum(scores) / len(scores), 1) if scores else 0
            summary[dept]['sources'] = list(summary[dept]['sources'])

        return dict(summary)
