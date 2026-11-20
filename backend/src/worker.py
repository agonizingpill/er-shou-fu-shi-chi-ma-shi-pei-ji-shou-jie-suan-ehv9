import os,time,pathlib,logging
import redis
from sqlalchemy import select
from .database import Session
from .models import FitAssessment,Measurement,FitProfile,BlindReview
from .common import lock,rows,get,dump
from .fit_model import predict
q=redis.from_url(os.environ['REDIS_URL'],decode_responses=True,socket_connect_timeout=1,socket_timeout=4)
while True:
 pathlib.Path('/artifacts/resale-heartbeat').write_text(str(time.time()))
 try:item=q.blpop('resale:fit',timeout=2)
 except redis.RedisError:
  logging.warning('Redis interrupted, retrying');time.sleep(1);continue
 if not item:continue
 with Session() as s:
  lock(s);x=s.get(FitAssessment,int(item[1]))
  if not x or x.state!='queued':continue
  blind=s.scalars(select(BlindReview).where(BlindReview.assessment_id==x.id)).first()
  if blind and blind.state=='failed':continue
  try:
   m=next(m for m in rows(s,Measurement) if m.garment_id==x.garment_id);p=get(s,FitProfile,x.profile_id);x.result=predict(dump(m),dump(p));x.state='ready'
  except Exception as e:
   x.state='failed';x.error=str(e)[:500];logging.exception('fit failed')
   if blind and blind.state in ['open','claimed']:blind.state='failed';blind.error='盲评预测计算失败，可重新开单'
  s.commit()
