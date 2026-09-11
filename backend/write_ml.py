import os

content = r'''
import random, math, hashlib
from datetime import datetime, timedelta
from collections import defaultdict
from itertools import combinations


class DemandPredictor:
    def __init__(self, trains, corridors):
        self.trains = trains
        self.corridors = {c['id']: c for c in corridors}
        self.historical = self._gen_history()

    def _gen_history(self):
        history = {}
        base = datetime.now() - timedelta(weeks=12)
        for w in range(12):
            for d in range(7):
                dt = base + timedelta(weeks=w, days=d)
                dow = dt.weekday()
                dow_m = [0.7,0.8,0.85,0.9,1.0,1.15,0.6][dow]
                trend = 1.0 + w * 0.008
                hourly = []
                for h in range(24):
                    if h <= 4: b = 5 + h*2
                    elif h <= 7: b = 30 + (h-5)*25
                    elif h <= 10: b = 85 - (h-8)*5
                    elif h <= 14: b = 55 - (h-11)*3
                    elif h <= 18: b = 50 + (h-15)*15
                    elif h <= 21: b = 90 - (h-19)*12
                    else: b = 40 - (h-21)*8
                    hourly.append(max(0, b * dow_m * trend + random.gauss(0,5)))
                history[dt.strftime('%Y-%m-%d')] = hourly
        return history

    def holt_winters(self, steps=168, alpha=0.3, beta=0.1, gamma=0.2):
        series = []
        for ds in sorted(self.historical.keys())[-7:]:
            series.extend(self.historical[ds])
        n = len(series)
        if n < 48:
            return [50.0]*steps
        period = 24
        level = sum(series[:period])/period
        trend = (sum(series[period:2*period])-sum(series[:period]))/(period*period)
        seasonal = [series[i]-level for i in range(period)]
        for i in range(period, n):
            val = series[i]
            nl = alpha*(val-seasonal[i%period]) + (1-alpha)*(level+trend)
            nt = beta*(nl-level) + (1-beta)*trend
            seasonal[i%period] = gamma*(val-nl) + (1-gamma)*seasonal[i%period]
            level, trend = nl, nt
        forecast = []
        for i in range(steps):
            forecast.append(max(0, round(level + trend*(i+1) + seasonal[(n+i)%period], 1)))
        return forecast

    def predict_route(self, origin, dest, date_str):
        hourly = self.holt_winters(24)
        rh = int(hashlib.md5(f'{origin}-{dest}'.encode()).hexdigest()[:8], 16)
        rw = 0.5 + (rh % 100)/100.0
        return {
            'hourly_demand': [round(h*rw,1) for h in hourly],
            'peak_hour': hourly.index(max(hourly)),
            'peak_demand': round(max(hourly)*rw,1),
            'total_daily': round(sum(hourly)*rw,0),
            'route_weight': round(rw,2),
        }

    def block_impact(self, start_h, end_h):
        hourly = self.holt_winters(24)
        impact = sum(hourly[start_h:end_h])
        alts = []
        for a in range(0, 24-(end_h-start_h)):
            ai = sum(hourly[a:a+(end_h-start_h)])
            alts.append({'start':a,'end':a+(end_h-start_h),'impact':round(ai,0),'savings':round(impact-ai,0)})
        alts.sort(key=lambda x: x['impact'])
        return {
            'affected_passengers': round(impact,0),
            'peak_in_window': round(max(hourly[start_h:end_h]),1) if end_h>start_h else 0,
            'impact_level': 'high' if impact>500 else 'medium' if impact>200 else 'low',
            'best_alternative': alts[0] if alts else None,
            'demand_curve': hourly,
        }


class EnergyOptimizer:
    TARIFF = {'peak':850,'off_peak':550,'night':320}
    CARBON = 0.82

    def __init__(self, trains, corridors, blocks):
        self.trains = trains
        self.corridors = {c['id']:c for c in corridors}
        self.blocks = blocks

    def _tariff(self, h):
        if 6<=h<=10 or 16<=h<=21:
            return self.TARIFF['peak']
        if 22<=h or h<=5:
            return self.TARIFF['night']
        return self.TARIFF['off_peak']

    def _pt(self, t):
        if not t:
            return 0
        p = t.split(':')
        return int(p[0]) + int(p[1])/60.0

    def optimize(self):
        total_cost = 0
        block_data = []
        for b in self.blocks:
            s = self._pt(b.get('start_time'))
            e = self._pt(b.get('end_time'))
            if e <= s:
                e += 24
            zid = b.get('zone_id')
            n_trains = len([t for t in self.trains if t.get('zone_id')==zid])
            cost = sum(n_trains * self._tariff((s+h)%24) for h in range(int(e-s)))
            total_cost += cost
            block_data.append({'block_id':b.get('block_id'),'cost':round(cost,0),'hours':round(e-s,1),'start_h':int(s),'n_trains':n_trains})
        improvements = []
        for bd in block_data:
            if 6 <= bd['start_h'] <= 21:
                night_cost = sum(bd['n_trains']*self._tariff((1+h)%24) for h in range(int(bd['hours'])))
                sav = bd['cost'] - night_cost
                if sav > 0:
                    improvements.append({'block_id':bd['block_id'],'current_start':bd['start_h'],'suggested_start':1,'current_cost':bd['cost'],'suggested_cost':round(night_cost,0),'savings':round(sav,0),'carbon_reduction':round(sav*self.CARBON/100,1)})
        improvements.sort(key=lambda x: x['savings'], reverse=True)
        total_sav = sum(i['savings'] for i in improvements)
        return {
            'current_cost': round(total_cost,0),
            'optimized_cost': round(total_cost-total_sav,0),
            'total_savings': round(total_sav,0),
            'savings_pct': round(total_sav/max(1,total_cost)*100,1),
            'improvements': improvements[:10],
            'night_blocks': sum(1 for b in self.blocks if self._pt(b.get('start_time'))<=5),
            'peak_blocks': sum(1 for b in self.blocks if 6<=self._pt(b.get('start_time'))<=10),
            'total_blocks': len(self.blocks),
        }


class CrewAssigner:
    SKILL = {
        'Track Inspector':{'Engineering':0.9,'Mechanical':0.3},
        'Signal Technician':{'Signal & Telecom':0.95,'Electrical':0.4},
        'OHE Maintainer':{'Traction Distribution':0.95,'Electrical':0.5},
        'Welder':{'Engineering':0.7,'Mechanical':0.6},
        'Section Engineer':{'Engineering':0.85,'Signal & Telecom':0.5,'Traction Distribution':0.5},
    }

    def __init__(self, crew, blocks):
        self.crew = crew
        self.blocks = blocks

    def _cost(self, c, b):
        role = c.get('role','')
        dept = b.get('dept_name','Engineering')
        skill = self.SKILL.get(role,{}).get(dept, 0.3)
        rem = c.get('max_hours',10) - c.get('hours_worked',0)
        pen = 0 if rem >= 4 else (4-rem)*10
        return round((1-skill)*100 + pen, 1)

    def assign(self):
        nc, nb = len(self.crew), len(self.blocks)
        if nc==0 or nb==0:
            return {'assignments':[],'unassigned':[],'utilization':[]}
        n = max(nc, nb)
        cm = [[1000.0]*n for _ in range(n)]
        for i,c in enumerate(self.crew):
            for j,b in enumerate(self.blocks):
                cm[i][j] = self._cost(c,b)
        for i in range(n):
            mn = min(cm[i])
            cm[i] = [v-mn for v in cm[i]]
        for j in range(n):
            mn = min(cm[i][j] for i in range(n))
            for i in range(n):
                cm[i][j] -= mn
        cands = [(cm[i][j],i,j) for i in range(nc) for j in range(nb)]
        cands.sort()
        assigns, ac, ab = [], set(), set()
        for cost,i,j in cands:
            if i not in ac and j not in ab:
                assigns.append({'crew_id':self.crew[i].get('crew_id'),'crew_name':self.crew[i].get('crew_name'),'role':self.crew[i].get('role'),'block_id':self.blocks[j].get('block_id'),'block_date':self.blocks[j].get('block_date'),'route':self.blocks[j].get('route_name','N/A'),'skill_cost':round(cost,1),'skill_match':round(max(0,100-cost),0),'status':'optimal' if cost<30 else 'good' if cost<60 else 'acceptable'})
                ac.add(i); ab.add(j)
        unassigned = [{'block_id':self.blocks[j].get('block_id'),'route':self.blocks[j].get('route_name','N/A'),'department':self.blocks[j].get('dept_name','?')} for j in range(nb) if j not in ab]
        util = []
        for i,c in enumerate(self.crew):
            n_a = len([a for a in assigns if a['crew_id']==c.get('crew_id')])
            hrs = n_a*4; mx = c.get('max_hours',10)
            pct = round(hrs/mx*100) if mx>0 else 0
            util.append({'crew_id':c.get('crew_id'),'name':c.get('crew_name'),'role':c.get('role'),'hours_used':hrs,'max_hours':mx,'utilization':pct,'blocks':n_a,'status':'optimal' if 60<=pct<=85 else 'underutilized' if pct<60 else 'overloaded'})
        return {
            'assignments': assigns,
            'unassigned': unassigned,
            'utilization': util,
            'avg_utilization': round(sum(u['utilization'] for u in util)/max(1,len(util)),1),
            'optimal': len([u for u in util if u['status']=='optimal']),
            'underutilized': len([u for u in util if u['status']=='underutilized']),
            'overloaded': len([u for u in util if u['status']=='overloaded']),
        }


class RLScheduler:
    def __init__(self, defects, blocks, trains):
        self.defects = defects
        self.blocks = blocks
        self.trains = trains

    def train(self, episodes=50, alpha=0.1, gamma=0.9, eps_start=0.9, eps_decay=0.95):
        n_states, n_actions = 10, 5
        qt = [[0.0]*n_actions for _ in range(n_states)]
        dept_names = ['Engineering','Traction Distribution','Signal & Telecom','Mechanical','Electrical']
        hist = []
        eps = eps_start
        best_r = float('-inf')
        best_sched = None
        dept_defects = defaultdict(list)
        for d in self.defects:
            dept_defects[d.get('department','Engineering')].append(d)
        for ep in range(episodes):
            state = min(n_states-1, len(self.defects)//3)
            if random.random() < eps:
                action = random.randint(0, n_actions-1)
            else:
                action = max(range(n_actions), key=lambda a: qt[state][a])
            dept = dept_names[action]
            crit = len([d for d in dept_defects.get(dept,[]) if d.get('severity')=='critical'])
            reward = crit*10 + random.randint(-5,15) - random.randint(5,20)
            ns = min(n_states-1, state+1)
            qt[state][action] += alpha*(reward + gamma*max(qt[ns]) - qt[state][action])
            if reward > best_r:
                best_r = reward
                best_sched = {'department':dept,'blocks_scheduled':random.randint(2,6),'reward':reward}
            hist.append({'episode':ep+1,'action':dept,'reward':round(reward,1),'epsilon':round(eps,3),'q_max':round(max(qt[state]),2)})
            eps *= eps_decay
        top_q = sorted([{'state':f'S{s}','action':dept_names[a],'q_value':round(qt[s][a],2)} for s in range(n_states) for a in range(n_actions) if qt[s][a]>0], key=lambda x: x['q_value'], reverse=True)[:15]
        early = [h['reward'] for h in hist[:10]]
        late = [h['reward'] for h in hist[-10:]]
        return {
            'episodes_run': episodes,
            'best_reward': round(best_r,1),
            'best_schedule': best_sched,
            'avg_early_reward': round(sum(early)/max(1,len(early)),1),
            'avg_late_reward': round(sum(late)/max(1,len(late)),1),
            'convergence_improvement': round((sum(late)-sum(early))/max(1,abs(sum(early)))*100,1),
            'episode_history': hist,
            'top_q_values': top_q,
            'final_epsilon': round(eps,4),
            'config': {'alpha':alpha,'gamma':gamma,'epsilon_start':eps_start,'epsilon_decay':eps_decay},
        }


class DigitalTwinSim:
    def __init__(self, corridors, trains, blocks):
        self.corridors = {c['id']:c for c in corridors}
        self.trains = trains
        self.blocks = blocks

    def simulate(self):
        sims = []
        total_delay = 0
        affected = 0
        for t in self.trains[:50]:
            dep = t.get('departure','10:00')
            if not dep:
                continue
            p = dep.split(':')
            dh = int(p[0]) + int(p[1])/60.0
            zid = t.get('zone_id')
            delay = 0
            cb = None
            for b in self.blocks:
                if b.get('zone_id') != zid:
                    continue
                bs = 0
                try:
                    bp = b.get('start_time','0:00').split(':')
                    bs = int(bp[0]) + int(bp[1])/60.0
                except:
                    pass
                be = bs + 3
                if bs <= dh <= be:
                    delay = random.randint(15, 90)
                    cb = b
                    break
            total_delay += delay
            if delay > 0:
                affected += 1
            sims.append({'train_number':t.get('number'),'train_name':t.get('name'),'origin':t.get('origin'),'destination':t.get('destination'),'departure':dep,'delay_minutes':delay,'conflicting_block':cb.get('block_id') if cb else None,'status':'delayed' if delay>0 else 'on_time'})
        impacts = []
        for b in self.blocks:
            aff = [s for s in sims if s.get('conflicting_block')==b.get('block_id')]
            impacts.append({'block_id':b.get('block_id'),'route':self.corridors.get(b.get('corridor_id'),{}).get('route_name','N/A'),'trains_delayed':len(aff),'total_delay_mins':sum(s['delay_minutes'] for s in aff)})
        return {
            'simulated_trains': len(sims),
            'trains_on_time': len([s for s in sims if s['status']=='on_time']),
            'trains_delayed': affected,
            'total_delay_minutes': total_delay,
            'avg_delay_minutes': round(total_delay/max(1,affected),1),
            'block_impacts': sorted(impacts,key=lambda x:x['total_delay_mins'],reverse=True)[:10],
            'timeline': sims[:30],
        }


class MultiZoneCoordinator:
    def __init__(self, corridors, trains, blocks):
        self.corridors = corridors
        self.trains = trains
        self.blocks = blocks

    def coordinate(self):
        zones = {}
        for c in self.corridors:
            zid = c.get('zone_id')
            if zid not in zones:
                zones[zid] = {'zone_name':c.get('zone_name'),'zone_code':c.get('zone_code'),'corridors':[],'blocks':0}
            zones[zid]['corridors'].append(c.get('route_name'))
        for b in self.blocks:
            zid = b.get('zone_id')
            if zid in zones:
                zones[zid]['blocks'] += 1
        xz_trains = []
        for t in self.trains:
            oz = t.get('origin_zone_id')
            dz = t.get('dest_zone_id')
            if oz and dz and oz != dz:
                xz_trains.append({'number':t.get('number'),'name':t.get('name'),'origin_zone':next((z.get('zone_name') for z in self.corridors if z.get('zone_id')==oz),'?'),'dest_zone':next((z.get('zone_name') for z in self.corridors if z.get('zone_id')==dz),'?'),'departure':t.get('departure')})
        conflicts = []
        zb = defaultdict(list)
        for b in self.blocks:
            zb[b.get('zone_id')].append(b)
        for z1 in zb:
            for z2 in zb:
                if z1 >= z2:
                    continue
                for b1 in zb[z1]:
                    for b2 in zb[z2]:
                        if b1.get('block_date')==b2.get('block_date'):
                            conflicts.append({'zone1':zones.get(z1,{}).get('zone_name','?'),'zone2':zones.get(z2,{}).get('zone_name','?'),'block1':b1.get('block_id'),'block2':b2.get('block_id'),'date':b1.get('block_date')})
        return {
            'zones': list(zones.values()),
            'cross_zone_trains': xz_trains[:15],
            'cross_zone_conflicts': conflicts[:10],
            'total_zones': len(zones),
            'total_cross_zone_trains': len(xz_trains),
        }


class PredictiveMaintenance:
    def __init__(self, defects):
        self.defects = defects

    def analyze(self):
        def defect_risk(d):
            sev = {'critical':0.9,'high':0.6,'medium':0.3,'low':0.1}.get(d.get('severity','low'),0.3)
            age = 1.0
            try:
                created = d.get('created_at','')
                if created:
                    cd = datetime.fromisoformat(created.replace('Z',''))
                    age = min(2.0, (datetime.now()-cd).days/30.0)
            except:
                pass
            return min(1.0, sev * (0.7 + age * 0.3))
        timeline = []
        for w in range(8):
            week_data = []
            for d in self.defects:
                risk = defect_risk(d)
                degradation = risk * (1 + w * 0.08)
                week_data.append({'defect_id':d.get('id'),'department':d.get('department'),'severity':d.get('severity'),'week':w+1,'risk_score':round(min(1.0, degradation),2),'status':'critical' if degradation>0.8 else 'warning' if degradation>0.5 else 'stable'})
            timeline.append({'week':w+1,'critical':len([x for x in week_data if x['status']=='critical']),'warning':len([x for x in week_data if x['status']=='warning']),'stable':len([x for x in week_data if x['status']=='stable']),'defects':week_data})
        summary = {
            'total_defects': len(self.defects),
            'critical_by_week4': len([d for d in self.defects if defect_risk(d)*(1+3*0.08)>0.8]),
            'critical_by_week8': len([d for d in self.defects if defect_risk(d)*(1+7*0.08)>0.8]),
        }
        return {'timeline':timeline,'summary':summary}


class NotificationEngine:
    def __init__(self, blocks, departments):
        self.blocks = blocks
        self.contacts = {
            'Engineering':{'head':'Chief Engineer','email':'eng@railway.gov.in','phone':'+91-9876543210'},
            'Traction Distribution':{'head':'Sr. DEE (Traction)','email':'trd@railway.gov.in','phone':'+91-9876543211'},
            'Signal & Telecom':{'head':'Chief Signal Engineer','email':'sig@railway.gov.in','phone':'+91-9876543212'},
        }

    def generate(self):
        notifs = []
        for b in self.blocks:
            dept = b.get('dept_name','Unknown')
            ct = self.contacts.get(dept,{'head':'Dept Head','email':'dept@railway.gov.in'})
            notifs.append({
                'id': 'NTF-%04d' % b.get('id', 0),
                'block_id': b.get('block_id'),
                'department': dept,
                'route': b.get('route_name','N/A'),
                'date': b.get('block_date'),
                'time': '%s-%s' % (b.get('start_time'), b.get('end_time')),
                'status': b.get('status'),
                'recipient': ct['head'],
                'email': ct['email'],
                'sent': b.get('status')=='approved',
                'acknowledged': b.get('status')=='completed',
            })
        pending = [n for n in notifs if not n['sent']]
        sent = [n for n in notifs if n['sent'] and not n['acknowledged']]
        acked = [n for n in notifs if n['acknowledged']]
        return {
            'total': len(notifs),
            'pending_approval': len(pending),
            'sent_awaiting_ack': len(sent),
            'acknowledged': len(acked),
            'notifications': notifs,
            'dept_contacts': self.contacts,
        }
'''

path = 'C:/Users/Abhinav/sih-railways/backend/ml_engine.py'
with open(path, 'w', encoding='utf-8') as f:
    f.write(content.strip())
print(f'Written {os.path.getsize(path)} bytes to ml_engine.py')
