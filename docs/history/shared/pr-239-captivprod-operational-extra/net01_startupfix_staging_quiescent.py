#!/usr/bin/env python3
import argparse,re,subprocess,sys
APP='captive-portal.service'
WD='captiv-net01-watchdog.service'
FAIL='captiv-net01-failsafe.service'
FW='captiv-net01-firewall.service'
UNITS=(APP,WD,FAIL,FW)
def run(args):
 p=subprocess.run(args,capture_output=True,text=True,timeout=5)
 if p.returncode:raise RuntimeError('status command failed: '+args[0])
 return p.stdout
def show(unit):
 data={}
 for line in run(['systemctl','show','--no-pager','-p','LoadState','-p','ActiveState','-p','SubState','-p','Job',unit]).splitlines():
  if '=' not in line:raise RuntimeError('malformed show')
  k,v=line.split('=',1)
  if k in data:raise RuntimeError('duplicate property')
  data[k]=v
 if set(data)!=set(('LoadState','ActiveState','SubState','Job')) or data['LoadState']!='loaded':raise RuntimeError('unit unavailable')
 if data['Job'] and not re.fullmatch('[1-9][0-9]*',data['Job']):raise RuntimeError('bad numeric job ID')
 return data
def jobs(mode):
 result={};ids=set()
 for line in run(['systemctl','list-jobs','--all','--no-legend','--plain']).splitlines():
  if not line.strip() or line.strip()=='No jobs running.':continue
  a=line.split()
  if len(a)!=4 or not re.fullmatch('[1-9][0-9]*',a[0]):raise RuntimeError('malformed list-jobs')
  jid,unit,typ,state=a
  if jid in ids or unit in result:raise RuntimeError('duplicate job')
  ids.add(jid)
  if mode!='install' or unit not in (APP,WD,FW) or typ!='start' or state not in ('waiting','running'):raise RuntimeError('unexpected pending job '+unit)
  result[unit]=(jid,typ,state)
 return result
def snapshot(mode):
 states={unit:show(unit) for unit in UNITS}
 listed=jobs(mode)
 for unit,v in states.items():
  j=listed.get(unit)
  if (v['Job'] or None)!=(j[0] if j else None):raise RuntimeError('Job ID mismatch '+unit)
  pair=(v['ActiveState'],v['SubState'])
  if unit in (APP,WD,FAIL):
   if pair!=('inactive','dead'):raise RuntimeError('not stopped '+unit)
   if unit==FAIL and j:raise RuntimeError('failsafe job')
  elif mode=='quiescent':
   if j or pair not in (('inactive','dead'),('active','exited')):raise RuntimeError('firewall not quiescent')
  elif pair==('activating','start'):
   if not j or j[1:]!=('start','running'):raise RuntimeError('firewall not actively starting')
  elif j or pair not in (('inactive','dead'),('active','exited')):raise RuntimeError('firewall unexpected state')
 return states,listed
def listener():
 for line in run(['ss','-H','-lnt']).splitlines():
  a=line.split()
  if len(a)<5 or a[0]!='LISTEN' or ':' not in a[3]:raise RuntimeError('bad ss')
  p=a[3].rsplit(':',1)[-1]
  if not p.isdigit():raise RuntimeError('bad ss port')
  if int(p)==18089:raise RuntimeError('port 18089 already listening')
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['install','quiescent'],default='quiescent')
 a=p.parse_args()
 try:
  first=snapshot(a.mode);listener()
  if snapshot(a.mode)!=first:raise RuntimeError('systemd changed during check')
  listener()
 except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as e:
  print('NET01_QUIESCENCE=HOLD '+str(e),file=sys.stderr);return 75
 print('NET01_QUIESCENCE=PASS mode='+a.mode);return 0
if __name__=='__main__':sys.exit(main())
