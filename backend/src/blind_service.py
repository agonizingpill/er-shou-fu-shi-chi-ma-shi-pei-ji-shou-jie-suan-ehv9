from .models import *
from .common import *

def _blinds(s,gid,pid):return [b for b in rows(s,BlindReview) if b.garment_id==gid and b.profile_id==pid]

def open_ticket(s,d,u):
 lock(s);g=garment(s,d['garment_id']);get(s,FitProfile,d['profile_id'])
 if not any(x.garment_id==g.id for x in rows(s,Measurement)):fail('未实测服饰不得封存预测')
 if g.state not in ['listed','held']:fail('服饰不在可试穿状态')
 blinds=_blinds(s,g.id,d['profile_id'])
 if any(b.state in ['open','claimed'] for b in blinds):fail('该衣物与体型已有未交卷的盲评单')
 if any(b.state=='submitted' for b in blinds):fail('该组合已完成盲评，请在原单上对照实穿判定')
 sealed={b.assessment_id for b in blinds}
 if any(a.garment_id==g.id and a.profile_id==d['profile_id'] and a.state in ['queued','ready'] and a.id not in sealed for a in rows(s,FitAssessment)):fail('该组合的普通适配预测已公开，不能再开盲评')
 x=FitAssessment(garment_id=g.id,profile_id=d['profile_id']);s.add(x);s.flush()
 y=BlindReview(garment_id=g.id,profile_id=d['profile_id'],assessment_id=x.id,opened_by=u['email'],note=d.get('note',''));s.add(y);s.flush();return y

def claim(s,id,u):
 lock(s);b=get(s,BlindReview,id)
 if b.state=='submitted':fail('盲评单已交卷，不能再领取')
 if b.state=='failed':fail('盲评预测已失败，请重新开单')
 if b.claimant:
  if b.claimant==u['email']:return b
  fail('盲评单只归一位领取人，其他顾问不能接手')
 b.claimant=u['email'];b.state='claimed';return b

def submit(s,id,d,u):
 c=lock(s);b=get(s,BlindReview,id)
 if b.state=='submitted':fail('盲评判定已交卷，重试不覆盖原判定')
 if b.state=='failed':fail('盲评预测已失败，不能交卷')
 if not b.claimant:fail('盲评单尚未领取，须先领取再交卷')
 if b.claimant!=u['email']:fail('只有领取人可以交卷')
 b.label=d['label'];b.note=d.get('note','');b.submitted_at=c.now;b.state='submitted';return b
