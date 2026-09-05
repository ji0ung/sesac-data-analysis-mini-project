#!/usr/bin/env python3
"""Read-only transport-newline hash gate. Never executes the generator or statistics."""
from pathlib import Path
import argparse, ast, hashlib, json, os, platform, sqlite3, subprocess, sys
from datetime import datetime
from zoneinfo import ZoneInfo

TS="260904_1149"; KST=ZoneInfo("Asia/Seoul")
APPROVED={
 "source":"a0cbf893663b99f1a2e4bb8f5e1c202f0a2467f7baccf01f9e858ff54d955571",
 "synthetic":"db80db7048add9c0c4cb1a985e67a77ae99bef3a30ce32bedb70cc0ee61dc896",
 "code":"b7e8cea58cc3fa653d9bcafe781a1d0be9f910cd0c5d1bc27ac04a2bddd1cf2a",
 "config":"59e588293184a0a9c7c704752a72f276e1e1184660767cf77c0179fee4987512",
 "qa_excel":"017ebccebfbdcef90bd3fad10db4e05d8370838662a8489d76461850a439d566",
 "qa_word":"ccde522907a188af23d5ff4042e4d6010a991dc12d7300e6cee92b885a918864",
 "qa_log":"eb6240e08d246d5648ecb77d59b50f54b9721daa39763c6e83b8c182f4fab731",
 "stage1_code":"2178b4d7d09a512f2750036ca5cfa864a6c9c8850e6abd9faf7af90ca2d64556",
 "stage1_manifest":"e804dd364465d8d36cdae974bc083a8e50025dc784997672099336cf2350e1c8",
 "parent":"af91c060a5eab8e69e3a190305c41238f6a9e53633de22b2efea6297156ed1cb"}
SIZES={"code":10195,"config":1174}
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):return sha_bytes(Path(p).read_bytes())
def rel(p,repo):
 try:return Path(p).resolve().relative_to(repo.resolve()).as_posix()
 except ValueError:return str(Path(p).resolve()).replace('\\','/')
def file_rec(role,p,repo,approved=None):
 p=Path(p);h=sha(p);return {"role":role,"path":rel(p,repo),"size_bytes":p.stat().st_size,"current_raw_sha256":h,"approved_sha256":approved,"pass":approved is None or h==approved}
def text_audit(p,approved,size,kind,parent):
 raw=Path(p).read_bytes();crlf=raw.count(b'\r\n');lf=raw.count(b'\n')-crlf;lcr=raw.count(b'\r')-crlf;norm=raw.replace(b'\r\n',b'\n');rawh=sha_bytes(raw);normh=sha_bytes(norm)
 out={"current_size":len(raw),"current_raw_sha256":rawh,"crlf_count":crlf,"lf_only_count":lf,"lone_cr_count":lcr,"utf8_bom":raw.startswith(b'\xef\xbb\xbf'),"final_newline":raw.endswith((b'\n',b'\r')),"lf_normalized_size":len(norm),"lf_normalized_sha256":normh,"size_difference":len(raw)-len(norm),"parent_approved_sha256":approved,"parent_approved_size":size}
 try:text=raw.decode('utf-8-sig' if out['utf8_bom'] else 'utf-8');out['utf8_strict_decode']=True
 except UnicodeDecodeError: text='';out['utf8_strict_decode']=False
 if kind=='python':
  try:tree=ast.parse(norm.decode('utf-8-sig' if out['utf8_bom'] else 'utf-8'));out['syntax_valid']=True;out['semantic_fingerprint_sha256']=sha_bytes(ast.dump(tree,include_attributes=False).encode())
  except Exception as e:out['syntax_valid']=False;out['syntax_error']=str(e);out['semantic_fingerprint_sha256']=None
 else:
  try:
   obj=json.loads(norm.decode('utf-8-sig' if out['utf8_bom'] else 'utf-8'));out['syntax_valid']=True;out['top_level_type']=type(obj).__name__;out['random_seed']=obj.get('random_seed') if isinstance(obj,dict) else None;out['semantic_fingerprint_sha256']=sha_bytes(json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode());out['parent_seed_consistent']=out['random_seed']==20260903 and parent.get('final_qa_status')=='PASS'
  except Exception as e:out['syntax_valid']=False;out['syntax_error']=str(e);out['semantic_fingerprint_sha256']=None;out['parent_seed_consistent']=False
 exact=rawh==approved
 crlf_ok=(not exact and normh==approved and lcr==0 and len(raw)-len(norm)==crlf and len(norm)==size and out['utf8_strict_decode'] and out['syntax_valid'] and (kind=='python' or (out.get('top_level_type')=='dict' and out.get('parent_seed_consistent'))))
 out['equivalence_class']='EXACT_RAW_MATCH' if exact else 'CRLF_TO_LF_ONLY' if crlf_ok else 'FAIL';out['pass']=exact or crlf_ok;return out
def db_audit(p,expected):
 c=sqlite3.connect(Path(p).resolve().as_uri()+'?mode=ro',uri=True);c.execute('pragma query_only=on');qo=c.execute('pragma query_only').fetchone()[0];integ=c.execute('pragma integrity_check').fetchone()[0]
 counts={t:c.execute(f'select count(*) from "{t}"').fetchone()[0] for t in expected if t!='sessions'}
 if 'sessions' in expected:counts['sessions']=c.execute('select count(distinct session_id) from search').fetchone()[0]
 c.close();return {"query_only":qo,"integrity_check":integ,"counts":counts,"expected_counts":expected,"pass":qo==1 and integ=='ok' and counts==expected}
def git(repo,relpaths):
 def run(args):
  x=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,encoding='utf-8',errors='replace');return {"returncode":x.returncode,"stdout":x.stdout.strip(),"stderr":x.stderr.strip()}
 d={"status":run(['status','--short','--',*relpaths]),"diff_ignore_eol":run(['diff','--ignore-space-at-eol','--',*relpaths]),"check_attr":run(['check-attr','text','eol','--',*relpaths]),"core_autocrlf":run(['config','--show-origin','--get','core.autocrlf']),"index_blobs":[]}
 for rp in relpaths:
  b=subprocess.run(['git','-C',str(repo),'show',':'+rp],capture_output=True).stdout
  d['index_blobs'].append({"path":rp,"available":bool(b),"size":len(b),"raw_sha256":sha_bytes(b) if b else None,"crlf_count":b.count(b'\r\n'),"lf_only_count":b.count(b'\n')-b.count(b'\r\n'),"lone_cr_count":b.count(b'\r')-b.count(b'\r\n')})
 return d
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=Path,required=True);ap.add_argument('--failed-check',type=Path,required=True);ap.add_argument('--parent',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();repo=a.repo.resolve();out=a.out.resolve();out.mkdir(parents=True,exist_ok=True)
 parent=json.loads(a.parent.read_text(encoding='utf-8'));failed=a.failed_check.read_text(encoding='utf-8');bundle=repo/'09_단계별 분석'/'2단계_1000건_증감_분석'/'02_관측형합성1000명_실행묶음_260903_1606_01';corr=a.parent.parent;s1=repo/'09_단계별 분석'/'1단계_원본_분석_및_가설_검증'/'01_원본분석_실행묶음_260903_1519_01'
 paths={"source":repo/'travel_data_filtered_complete_2026-09-03_v02_비식별.sqlite',"synthetic":bundle/'호텔검색_관측형합성1000명_데이터_260903_1606_01.sqlite',"code":bundle/'호텔검색_관측형합성1000명_생성코드_260903_1606_01.py',"config":bundle/'호텔검색_관측형합성1000명_생성설정_260903_1606_01.json',"qa_excel":corr/'호텔검색_관측형합성1000명_QA교정결과_260903_1745_02.xlsx',"qa_word":corr/'호텔검색_관측형합성1000명_QA교정보고서_260903_1745_02.docx',"qa_log":corr/'호텔검색_관측형합성1000명_QA교정실행기록_260903_1745_02.md',"stage1_code":s1/'호텔검색_원본분석_재현코드_260903_1519_01.py',"stage1_manifest":s1/'호텔검색_원본분석_실행묶음매니페스트_260903_1519_01.json'}
 files=[file_rec(k,p,repo,APPROVED[k]) for k,p in paths.items()]
 ta={"generation_code":text_audit(paths['code'],APPROVED['code'],SIZES['code'],'python',parent),"generation_config":text_audit(paths['config'],APPROVED['config'],SIZES['config'],'json',parent)}
 dba={"source":db_audit(paths['source'],{"user":89,"search":296,"search_filter":296,"search_result":8555,"event":10432,"booking":36}),"synthetic":db_audit(paths['synthetic'],{"user":1000,"search":6900,"booking":0,"sessions":1000})}
 relpaths=[rel(paths['code'],repo),rel(paths['config'],repo)];gd=git(repo,relpaths)
 parent_ok=sha(a.parent)==APPROVED['parent'] and parent.get('final_qa_status')=='PASS' and all(v=='PASS' for v in parent.get('G1_G5',{}).values()) and parent.get('expansion_allowed') is True and ta['generation_config'].get('random_seed')==20260903
 binary_ok=all(x['pass'] for x in files if x['role'] not in ('code','config'))
 failed_ok='BUNDLE_RUN_TS`: `260904_1133`' in failed and 'STEP1=FAIL' in failed
 gate=parent_ok and binary_ok and all(x['pass'] for x in ta.values()) and all(x['pass'] for x in dba.values()) and failed_ok
 status='PASS' if gate else 'FAIL';code_path=Path(__file__).resolve();now=datetime.now(KST).isoformat(timespec='seconds')
 md=out/f'호텔검색_관측형합성1000명_해시정규화점검_{TS}_01.md'
 lines=[f'# 해시 정규화 보완 게이트', '',f'- `HASH_GATE={status}`',f'- `STEP1={status}`',f'- BUNDLE_RUN_TS: `{TS}`',f'- 검증 시각(KST): `{now}`','', '## 텍스트 바이트 검증','', '| 파일 | 승인 SHA | 현재 SHA | LF 정규화 SHA | CRLF | LF-only | lone CR | 현재/정규화 크기 | 판정 |','|---|---|---|---|---:|---:|---:|---|---|']
 for k,n in [('generation_code','생성 코드'),('generation_config','config')]:
  x=ta[k];lines.append(f"| {n} | `{x['parent_approved_sha256']}` | `{x['current_raw_sha256']}` | `{x['lf_normalized_sha256']}` | {x['crlf_count']} | {x['lf_only_count']} | {x['lone_cr_count']} | {x['current_size']}/{x['lf_normalized_size']} | {x['equivalence_class']} |")
 lines += ['', '## 필수 입력·DB 검증','',f'- 부모 매니페스트: `{rel(a.parent,repo)}` / `{sha(a.parent)}` / PASS={parent_ok}',f'- 실패 진입점검: `{rel(a.failed_check,repo)}` / `{sha(a.failed_check)}` / 내부 TS 확인={failed_ok}',f"- 원본 DB: raw SHA 일치={next(x for x in files if x['role']=='source')['pass']}, query_only={dba['source']['query_only']}, integrity={dba['source']['integrity_check']}, 행 수 일치={dba['source']['counts']==dba['source']['expected_counts']}",f"- 합성 DB: raw SHA 일치={next(x for x in files if x['role']=='synthetic')['pass']}, query_only={dba['synthetic']['query_only']}, integrity={dba['synthetic']['integrity_check']}, 행 수 일치={dba['synthetic']['counts']==dba['synthetic']['expected_counts']}",f'- 나머지 필수 바이너리·QA 원시 해시 일치={binary_ok}','', '## Git 읽기 전용 진단','',f"- core.autocrlf: `{gd['core_autocrlf']['stdout']}`",f"- check-attr: `{gd['check_attr']['stdout']}`",f"- status: `{gd['status']['stdout'] or '(clean for both files)'}`",f"- diff --ignore-space-at-eol: `{gd['diff_ignore_eol']['stdout'] or '(no diff)'}`",'- Git 진단은 원인 보조 근거일 뿐 해시 PASS를 대체하지 않았다.','', '## 불변·금지 확인','', '- 기존 파일 수정 없음','- 생성기 미실행, 통계검정 미실행','- 10,000명·STRESS·S1~S3·OVERSAMPLED·SX/A3·BOOKING/예약 이벤트 미생성']
 md.write_text('\n'.join(lines),encoding='utf-8')
 if not gate:print(json.dumps({"HASH_GATE":status,"STEP1":status,"audit":ta,"markdown":str(md)},ensure_ascii=False,indent=2));return
 addp=out/f'호텔검색_관측형합성1000명_해시정규화보완매니페스트_{TS}_01.json'
 add={"schema_version":"1.0","artifact_type":"TRANSPORT_NORMALIZATION_ADDENDUM","BUNDLE_RUN_TS":TS,"parent_corrected_manifest":{"path":rel(a.parent,repo),"sha256":sha(a.parent)},"failed_entry_check":{"path":rel(a.failed_check,repo),"sha256":sha(a.failed_check)},"verification_code":{"path":rel(code_path,repo),"raw_sha256":sha(code_path)},"all_input_files":files,"text_transport_audit":ta,"database_audit":dba,"git_diagnostics":gd,"environment":{"python":sys.version,"platform":platform.platform(),"core_autocrlf":gd['core_autocrlf']['stdout']},"HASH_GATE":"PASS","existing_files_unchanged":True,"generator_executed":False,"statistical_tests_executed":False,"forbidden_data_generated":False,"created_at_kst":now}
 addp.write_text(json.dumps(add,ensure_ascii=False,indent=2),encoding='utf-8')
 ctxp=out/f'호텔검색_관측형합성1000명_전체가설분석컨텍스트_{TS}_01.json'
 metrics={"B3_IMMEDIATE_RECOVERY":{"original":"24/140=17.14%","synthetic":"558/3271=17.06%"},"B3_SESSION_FINAL_RECOVERY":{"original":"21/28=75.00%","synthetic":"488/651=74.96%"},"DIAG_FIRST_SEARCH_ZERO_RECOVERY":{"original":"4/6=66.67%","synthetic":"92/139=66.19%","classification":"diagnostic, not B3 session final recovery"}}
 ctx={"step1_status":"PASS","hash_gate_status":"PASS","BUNDLE_RUN_TS":TS,"parent_corrected_manifest":{"path":rel(a.parent,repo),"sha256":sha(a.parent)},"transport_normalization_addendum":{"path":rel(addp,repo),"sha256":sha(addp)},"failed_entry_check":{"path":rel(a.failed_check,repo),"sha256":sha(a.failed_check)},"source_db":{"path":rel(paths['source'],repo),"raw_sha256":sha(paths['source'])},"synthetic_db":{"path":rel(paths['synthetic'],repo),"raw_sha256":sha(paths['synthetic'])},"all_followup_inputs":files,"generation_code_hashes":ta['generation_code'],"config_hashes":ta['generation_config'],"binary_hash_policy":"RAW_SHA256_EXACT","text_hash_policy":"RAW_SHA256_PINNED_AND_LF_NORMALIZED_PARENT_MATCH","parent_expansion_allowed":True,"existing_s0_1000_hypothesis_analysis_allowed":True,"this_workflow_10000_generation_allowed":False,"generator_execution_allowed":False,"prohibited":["A3","BOOKING","booking events","STRESS_02","STRESS_05","STRESS_10","S1","S2","S3","OVERSAMPLED","SX","10000 generation"],"B3_metric_ids":metrics,"next_step":"PROMPT_2_FULL_HYPOTHESIS_CALCULATION"}
 ctxp.write_text(json.dumps(ctx,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({"HASH_GATE":"PASS","STEP1":"PASS","audit":ta,"outputs":{"code":{"path":str(code_path),"sha256":sha(code_path)},"markdown":{"path":str(md),"sha256":sha(md)},"addendum":{"path":str(addp),"sha256":sha(addp)},"context":{"path":str(ctxp),"sha256":sha(ctxp)}}},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
