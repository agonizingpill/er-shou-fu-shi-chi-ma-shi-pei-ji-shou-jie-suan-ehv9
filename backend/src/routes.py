import os,redis
from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from .database import Session
from .models import *
from .schemas import *
from .common import *
from .security import current,allow
from . import consignment_service as consignment,fit_service as fit,fitting_service as fitting,sale_service as sale,return_service as returns,settlement_service as settlement,blind_service as blind
router=APIRouter()
def change(u,action,fn,supervisor=False):
 allow(u,*(['supervisor'] if supervisor else ['operator','supervisor']))
 with Session() as s:x=fn(s);audit(s,u,action,x);s.commit();return dump(x)
def enqueue(id,error):
 try:redis.from_url(os.environ['REDIS_URL'],socket_connect_timeout=1,socket_timeout=2).rpush('resale:fit',id)
 except Exception:
  with Session() as s:
   x=s.get(FitAssessment,id);x.state='failed';x.error=error
   b=s.scalars(select(BlindReview).where(BlindReview.assessment_id==id)).first()
   if b:b.state='failed';b.error=error
   s.commit()
  raise HTTPException(503,error)
@router.get('/register')
def register(u=Depends(current)):
 with Session() as s:
  blind_models=rows(s,BlindReview)
  sealed={b.assessment_id for b in blind_models if b.state in ['open','claimed']}
  ready={a.id for a in rows(s,FitAssessment) if a.state=='ready'}
  data={n:[dump(x) for x in rows(s,c)] for n,c in [('consignors',Consignor),('agreements',Agreement),('amendments',Amendment),('garments',Garment),('measurements',Measurement),('profiles',FitProfile),('assessments',FitAssessment),('blinds',BlindReview),('fittings',Fitting),('sales',Sale),('returns',Return),('payouts',Payout),('withdrawals',Withdrawal),('clock',Shop)]}
  for b in data['blinds']:b['prediction_ready']=b['assessment_id'] in ready
  data['assessments']=[a for a in data['assessments'] if a['id'] not in sealed]
  return data
@router.get('/audit')
def audits(u=Depends(current)):
 with Session() as s:return [dump(x) for x in rows(s,Audit)]
@router.post('/consignors')
def consignors(d:ConsignorIn,u=Depends(current)):return change(u,'寄售人登记',lambda s:consignment.consignor(s,d.model_dump()))
@router.post('/agreements')
def agreements(d:AgreementIn,u=Depends(current)):return change(u,'寄售协议',lambda s:consignment.agreement(s,d.model_dump()))
@router.post('/agreements/{id}/commission')
def amend(id:int,d:AmendmentIn,u=Depends(current)):return change(u,'佣金修订',lambda s:consignment.amend(s,id,d.model_dump()),True)
@router.post('/garments')
def garments(d:GarmentIn,u=Depends(current)):return change(u,'入店验衣',lambda s:consignment.intake(s,d.model_dump()))
@router.post('/measurements')
def measurements(d:MeasurementIn,u=Depends(current)):return change(u,'服饰实测',lambda s:fit.measure(s,d.model_dump()))
@router.post('/profiles')
def profiles(d:ProfileIn,u=Depends(current)):return change(u,'匿名体型',lambda s:fit.profile(s,d.model_dump()))
@router.post('/assessments')
def assessments(d:AssessmentIn,u=Depends(current)):
 d=change(u,'适配计算',lambda s:fit.assess(s,d.model_dump()))
 enqueue(d['id'],'适配队列暂时不可达，记录已标记失败，可重新提交')
 return d
@router.post('/blind-reviews')
def blind_open(d:BlindReviewIn,u=Depends(current)):
 x=change(u,'盲评开单',lambda s:blind.open_ticket(s,d.model_dump(),u),True)
 enqueue(x['assessment_id'],'盲评预测入队失败，盲评单已失效，可重新开单')
 return x
@router.post('/blind-reviews/{id}/claim')
def blind_claim(id:int,u=Depends(current)):return change(u,'盲评领取',lambda s:blind.claim(s,id,u))
@router.post('/blind-reviews/{id}/submit')
def blind_submit(id:int,d:BlindSubmitIn,u=Depends(current)):return change(u,'盲评交卷',lambda s:blind.submit(s,id,d.model_dump(),u))
@router.post('/fittings')
def fittings(d:FittingIn,u=Depends(current)):return change(u,'排他留衣',lambda s:fitting.reserve(s,d.model_dump()))
@router.post('/fittings/{id}/cancel')
def cancel(id:int,u=Depends(current)):return change(u,'取消试衣',lambda s:fitting.cancel(s,id))
@router.post('/sales')
def sales(d:SaleIn,u=Depends(current)):return change(u,'试衣成交',lambda s:sale.sell(s,d.model_dump()))
@router.post('/returns')
def ret(d:ReturnIn,u=Depends(current)):return change(u,'适配退货',lambda s:returns.request(s,d.model_dump()))
@router.post('/returns/{id}/inspect')
def inspect(id:int,d:InspectionIn,u=Depends(current)):return change(u,'退衣复检',lambda s:returns.inspect(s,id,d.model_dump()),True)
@router.post('/payouts')
def payouts(d:PayoutIn,u=Depends(current)):return change(u,'寄售结算',lambda s:settlement.payout(s,d.model_dump()),True)
@router.post('/garments/{id}/withdraw')
def withdraw(id:int,d:ReasonIn,u=Depends(current)):return change(u,'期满撤回',lambda s:settlement.withdraw(s,id,d.model_dump()),True)
@router.post('/clock')
def clock(d:ClockIn,u=Depends(current)):return change(u,'推进演示时钟',lambda s:settlement.clock(s,d.model_dump()),True)
