"""Native, transactional inventory. No entities, device registry, or commissioning."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
import math
import re
from .matter import parse_code, format_code
from .text_recognition import recognise_identity

ICONS={'','bulb','switch','plug','sensor'}
LIMIT=10000


def now():
    return datetime.now(timezone.utc).isoformat()


class InventoryError(ValueError):
    def __init__(self,message,status=400,conflicts=None):
        super().__init__(message)
        self.status=status
        self.conflicts=conflicts


def fields(item,existing=None,backup=False):
    if not isinstance(item,dict):raise InventoryError('Invalid device details.')
    result={}
    for key,limit in [('brand',120),('product',160),('name',160),('notes',2000)]:
        value=item.get(key,'')
        if not isinstance(value,str) or len(value)>limit:raise InventoryError(f'{key.capitalize()} must be text under {limit} characters.')
        result[key]=value if backup else value.strip()
    for key in ['color','icon']:
        value=item.get(key,existing.get(key,'') if existing else '')
        if not isinstance(value,str):raise InventoryError(f'Invalid {key}.')
        value=value.strip().lower()
        if key=='color' and value and not re.fullmatch('#[0-9a-f]{6}',value):raise InventoryError('Choose a valid colour in #RRGGBB format.')
        if key=='icon' and value not in ICONS:raise InventoryError('Choose a supported device icon.')
        result[key]=value
    parsed=parse_code(item.get('qr_payload') or item.get('manual_code',''))
    if item.get('qr_payload') and item.get('manual_code') and parse_code(item['manual_code'])['manual_code']!=parsed['manual_code']:
        raise InventoryError('The QR payload and manual code do not match.')
    result.update(parsed)
    if backup:
        for key in ['created_at','updated_at']:
            if key not in item:continue
            value=item[key]
            if not isinstance(value,str) or len(value)>40:raise InventoryError('Invalid backup date.')
            date=datetime.fromisoformat(value.replace('Z','+00:00'))
            if date.tzinfo is None:raise InventoryError('Backup dates must include a timezone.')
            result[key]=value
    return result


def import_records(items):
    if not isinstance(items,list) or len(items)>LIMIT:raise InventoryError('Choose a backup containing up to 10,000 devices.')
    result=[];seen=set()
    for item in items:
        record=fields(item,backup=True)
        if record['manual_code'] in seen:raise InventoryError('The same pairing code appears more than once in this backup.')
        seen.add(record['manual_code']);result.append(record)
    return result


class Inventory:
    def __init__(self,store):
        self.store=store
        self.data={'devices':[],'next_id':1}
        self.lock=asyncio.Lock()

    async def load(self):
        saved=await self.store.async_load()
        if saved is None:return
        if not isinstance(saved,dict):raise InventoryError('Invalid saved inventory.')
        rows=saved.get('devices')
        import_records(rows)
        ids=[row.get('id') for row in rows]
        if any(type(value) is not int or value<1 for value in ids) or len(set(ids))!=len(ids):raise InventoryError('Invalid saved device IDs.')
        if any(type(row.get('revision')) is not int or row['revision']<1 for row in rows):raise InventoryError('Invalid saved revisions.')
        next_id=saved.get('next_id')
        if type(next_id) is not int or next_id<=max(ids,default=0):raise InventoryError('Invalid saved inventory sequence.')
        self.data=deepcopy(saved)

    async def request(self,method,path,body=None):
        try:
            async with self.lock:
                data=deepcopy(self.data)
                status,result,changed=self.dispatch(data,method,path.strip('/'),body or {})
                if changed:
                    if len(data['devices'])>LIMIT:raise InventoryError('Inventory is limited to 10,000 devices.')
                    await self.store.async_save(data)
                    self.data=data
                return {'status':status,'body':deepcopy(result)}
        except ValueError as error:
            response={'error':str(error)}
            if isinstance(error,InventoryError) and error.conflicts is not None:response['conflicts']=error.conflicts
            return {'status':getattr(error,'status',400),'body':response}

    def dispatch(self,data,method,path,body):
        rows=data['devices'];by_code={d['manual_code']:d for d in rows};by_id={d['id']:d for d in rows}
        if method=='GET' and path=='api/devices':return 200,sorted(rows,key=lambda d:-d['id']),False
        if method=='GET' and path=='api/export':return 200,{'version':1,'exported_at':now(),'devices':sorted(rows,key=lambda d:d['id'])},False
        if method=='POST' and path=='api/validate':return 200,parse_code(body.get('code')),False
        if method=='POST' and path=='api/recognize':return 200,recognize(body),False
        if method=='POST' and path=='api/import/preview':
            backup=body.get('backup')
            if not isinstance(backup,dict) or type(backup.get('version')) is not int or backup['version']!=1:raise InventoryError('Choose a supported Matterbase JSON backup (version 1).')
            return 200,{'devices':[{'device':d,'original':by_code.get(d['manual_code'])} for d in import_records(backup.get('devices'))]},False
        if method=='POST' and path=='api/import':
            items=body.get('devices')
            if not isinstance(items,list):raise InventoryError('Preview a backup before importing it.')
            records=import_records([i.get('device') if isinstance(i,dict) else None for i in items])
            created=updated=skipped=0
            for item,record in zip(items,records):
                action=item.get('action');original=by_code.get(record['manual_code'])
                if action=='skip':skipped+=1;continue
                if action=='overwrite':
                    if not original or type(item.get('expected_id')) is not int or type(item.get('expected_revision')) is not int or item['expected_id']!=original['id'] or item['expected_revision']!=original['revision']:
                        raise InventoryError('A saved device changed after preview. Preview the backup again; no changes were made.',409)
                    original.update(record);original['revision']+=1;updated+=1
                elif action=='add':
                    if original:raise InventoryError('A code was saved after preview. Preview the backup again; no changes were made.',409)
                    self.insert(data,record);created+=1
                else:raise InventoryError('Choose Add, Skip, or Overwrite for each device.')
            return 200,{'created':created,'updated':updated,'skipped':skipped},bool(created or updated)
        if method=='POST' and path=='api/devices':
            items=body.get('devices')
            if not isinstance(items,list) or not 1<=len(items)<=100:raise InventoryError('Add between 1 and 100 devices at a time.')
            records=[];conflicts={};seen=set()
            for item in items:
                record=fields(item);code=record['manual_code']
                if code in seen:raise InventoryError('The same pairing code appears twice in this batch. No changes were made.',409)
                seen.add(code);target=item.get('overwrite_id');original=by_code.get(code)
                if 'overwrite_id' in item:
                    revision=item.get('expected_revision')
                    if type(target) is not int or target<1 or type(revision) is not int or revision<1:raise InventoryError('Overwriting requires a saved device ID and its current revision.')
                    original=by_id.get(target)
                    if not original:raise InventoryError('The original device no longer exists. No changes were made.',409)
                    if original['manual_code']!=code:raise InventoryError('An overwrite must use the original device’s pairing code.')
                    if original['revision']!=revision:conflicts[target]=original
                    record=fields({**original,**item,'qr_payload':item.get('qr_payload') or original['qr_payload']},original)
                elif original:conflicts[original['id']]=original
                records.append((record,target))
            if conflicts:raise InventoryError('These codes are already saved, or an original changed. Choose Exclude or Overwrite again. No changes were made.',409,list(conflicts.values()))
            updated=0
            for record,target in records:
                if target is not None:
                    original=by_id[target];original.update(record);original.update(revision=original['revision']+1,updated_at=now());updated+=1
                else:self.insert(data,record)
            created=len(records)-updated
            return 201 if created else 200,{'saved':len(records),'created':created,'updated':updated},True
        match=re.fullmatch(r'api/devices/([1-9][0-9]*)',path)
        if match and method in ('PUT','DELETE'):
            original=by_id.get(int(match[1]))
            if not original:raise InventoryError('Device not found.',404)
            if method=='DELETE':rows.remove(original);return 204,None,True
            record=fields(body,original)
            other=by_code.get(record['manual_code'])
            if other and other['id']!=original['id']:raise InventoryError('This pairing code belongs to another saved device.',409)
            original.update(record);original.update(revision=original['revision']+1,updated_at=now())
            return 200,{'saved':1},True
        raise InventoryError('Unknown inventory operation.',404)

    def insert(self,data,record):
        stamp=now()
        data['devices'].append({'id':data['next_id'],'revision':1,'created_at':stamp,'updated_at':stamp,**record})
        data['next_id']+=1


def recognize(body):
    barcodes=body.get('barcodes',[]);lines=body.get('lines',[]);width=body.get('width',1);height=body.get('height',1)
    if (not isinstance(barcodes,list) or len(barcodes)>200 or not isinstance(lines,list) or len(lines)>2000 or
        any(type(n) not in (int,float) or not math.isfinite(n) or not 1<=n<=3200 for n in (width,height))):raise InventoryError('Invalid recognition result.')
    safe_lines=[]
    for line in lines:
        if not isinstance(line,dict) or not isinstance(line.get('text'),str) or len(line['text'])>1000:raise InventoryError('Invalid recognised text.')
        safe={key:line.get(key,0) for key in ('x','y','w','h','confidence')}
        if any(type(n) not in (int,float) or not math.isfinite(n) or abs(n)>100000 for n in safe.values()):raise InventoryError('Invalid text bounds.')
        safe.update(text=line['text'],words=[])
        words=line.get('words',[])
        if not isinstance(words,list) or len(words)>200:raise InventoryError('Invalid recognised words.')
        for word in words:
            if not isinstance(word,dict) or not isinstance(word.get('text'),str) or len(word['text'])>200 or type(word.get('confidence')) not in (int,float) or not math.isfinite(word['confidence']):raise InventoryError('Invalid recognised word.')
            safe['words'].append({'text':word['text'],'confidence':word['confidence']})
        safe_lines.append(safe)
    text='\n'.join(line['text'] for line in safe_lines);codes={};ignored=0
    for barcode in barcodes:
        if not isinstance(barcode,dict) or not isinstance(barcode.get('text'),str) or len(barcode['text'])>4096:raise InventoryError('Invalid barcode.')
        if not barcode['text'].upper().startswith('MT:'):ignored+=1;continue
        bounds=barcode.get('bounds')
        if bounds is not None and (not isinstance(bounds,list) or len(bounds)!=4 or any(type(n) not in (int,float) or not math.isfinite(n) or abs(n)>10000 for n in bounds)):raise InventoryError('Invalid barcode bounds.')
        for payload in barcode['text'].split('*'):
            try:parsed=parse_code(payload if payload.upper().startswith('MT:') else 'MT:'+payload)
            except ValueError:ignored+=1;continue
            color=barcode.get('color','');icon=barcode.get('icon','')
            appearance={'color':color if isinstance(color,str) and re.fullmatch('#[0-9a-fA-F]{6}',color) else '', 'icon':icon if isinstance(icon,str) and icon in ICONS else ''}
            if any(appearance.values()):appearance['appearance_source']='label'
            codes[parsed['manual_code']]={**parsed,**appearance,'_bounds':bounds,'source':'qr'}
    for match in re.finditer(r'(?<!\d)(?:\d{4}[\s\-–—·:]+\d{3}[\s\-–—·:]+\d{4}|\d{11}|\d{21})(?!\d)',text):
        try:parsed=parse_code(re.sub(r'\D','',match.group()))
        except ValueError:continue
        codes.setdefault(parsed['manual_code'],{**parsed,'source':'text'})
    identity=recognise_identity(safe_lines,codes.values(),(width,height))
    for code in codes.values():code['display_code']=format_code(code['manual_code'])
    notice=body.get('notice','')
    if not isinstance(notice,str) or len(notice)>500:raise InventoryError('Invalid recognition notice.')
    return {'codes':list(codes.values()),'text':text,'suggestions':identity['products'],'identity':identity,'ignored':ignored,'notice':notice}
