#!/usr/bin/env python3
"""Approved paired A/B synthetic generator (production-capable, not observed A/B data)."""
from __future__ import annotations

import argparse, csv, hashlib, importlib.metadata, json, math, os, random, sqlite3, sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jsonschema
import yaml

HERE = Path(__file__).resolve().parent
SCHEMA_SQL = HERE / "02_schema_prod.sql"
CONFIG_SCHEMA = HERE / "02_config_schema_prod.json"
APPROVED_CONFIG_SHA256 = "fb7076938a2f4dc5819772328c79c3944533351e719d51f4e05db163ecf1ffac"
RUN_TIME = "2026-09-07T00:00:00+00:00"
POLICIES = {
    "condition_keeper": "동일 조건 반복 경고와 완화 대안 비교",
    "location_flexible": "인접지역 확대",
    "budget_flexible": "가격 범위 확대",
    "option_count_flexible": "요구 옵션 수 감소",
    "query_reframer": "연관 검색어·자동완성",
    "rapid_resolver": "복합 제약의 단계적 완화",
}

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1<<20),b""): h.update(b)
    return h.hexdigest()

def fp(path: Path) -> dict[str,Any]:
    s=path.stat(); return {"sha256":sha256(path),"bytes":s.st_size,"mtime_ns":s.st_mtime_ns}

def resolve(config_path: Path, value: str) -> Path:
    p=Path(value); return p.resolve() if p.is_absolute() else (config_path.parent/p).resolve()

def load_config(path: Path) -> dict[str,Any]:
    cfg=yaml.safe_load(path.read_text(encoding="utf-8"))
    schema=json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema).validate(cfg)
    validate_production_config(cfg)
    return cfg

def validate_production_config(c: dict[str,Any]) -> None:
    if (c["n_users_total"],c["n_users_control"],c["n_users_treatment"],c["max_users_allowed"]) != (10000,5000,5000,10000):
        raise ValueError("production population must be exactly 10000=5000+5000")
    if c["n_users_total"] != c["n_users_control"]+c["n_users_treatment"]:
        raise ValueError("arm counts do not sum to total")
    if not c["require_paired_assignment"] or not c["allow_full_generation"]:
        raise ValueError("paired/full-generation guards must be enabled")

def validate_execution(c:dict[str,Any], config_path:Path, dry_run_users:int|None, confirm:bool, supplied_hash:str|None, output:Path) -> tuple[str,int]:
    approved=Path(c["approved_output_dir"]).resolve()
    if dry_run_users is not None:
        if dry_run_users<2 or dry_run_users>200 or dry_run_users%2: raise ValueError("dry_run permits an even population from 2 through 200 only")
        return "dry_run",dry_run_users
    if c["execution_mode"]!="production": raise ValueError("full run requires execution_mode=production")
    if not confirm: raise PermissionError("--confirm-production is required")
    actual=sha256(config_path)
    if supplied_hash!=actual or actual!=APPROVED_CONFIG_SHA256: raise PermissionError("approved config SHA-256 mismatch")
    if output.parent.resolve()!=approved: raise PermissionError("unapproved output folder")
    if not approved.is_dir() or any(approved.iterdir()): raise FileExistsError("approved output folder must exist and be empty")
    return "production",10000

def packages()->dict[str,str]:
    d={"python":sys.version.split()[0],"sqlite":sqlite3.sqlite_version}
    for x in ("PyYAML","jsonschema"): d[x]=importlib.metadata.version(x)
    return d

def posterior_draws(path:Path,rng:random.Random)->dict[str,float]:
    out={}
    with path.open(encoding="utf-8-sig",newline="") as f:
        for r in csv.DictReader(f):
            if r["distribution"].lower()=="beta": out[r["parameter_id"]]=rng.betavariate(float(r["posterior_alpha"]),float(r["posterior_beta"]))
    return out

def make_profiles(n_pairs:int,rng:random.Random,base_recovery:float)->list[dict[str,Any]]:
    intents=list(POLICIES); regions=["metro","coastal","inland","island"]
    states=["none","price_only","option_only","price_option","multi_constraint"]
    profiles=[]
    for i in range(n_pairs):
        intent=intents[i%len(intents)]; region=regions[(i//len(intents))%len(regions)]; state=states[(i*7+i//23)%len(states)]
        price=int(state in ("price_only","price_option","multi_constraint")); option=int(state in ("option_only","price_option","multi_constraint"))
        profiles.append(dict(pair_id=f"P{i+1:05d}",intent=intent,region=region,state=state,price=price,option=option,
          propensity=1+rng.randrange(4),base_recovery=max(.01,min(.99,base_recovery+rng.uniform(-.12,.12))),
          u_zero=rng.random(),u_behavior=rng.random(),u_recovery=rng.random(),u_detail=rng.random(),
          cluster=f"TC-{intent[:3]}-{region[:2]}-{state[:3]}-{i%97:02d}"))
    rng.shuffle(profiles); return profiles

def insert_dims(db:sqlite3.Connection)->None:
    for h in range(1,61):
        db.execute("INSERT INTO HotelDimension VALUES(?,?,?,?)",(h,f"HC{h:03d}",["metro","coastal","inland","island"][h%4],["economy","standard","premium"][h%3]))
        for k in range(2): db.execute("INSERT INTO RoomDimension VALUES(?,?,?,?)",((h-1)*2+k+1,h,["standard","family"][k],2+k*2))

def generate(config_path:Path,output:Path,dry_run_users:int|None=None,confirm:bool=False,approved_hash:str|None=None)->dict[str,Any]:
    c=load_config(config_path); mode,n=validate_execution(c,config_path,dry_run_users,confirm,approved_hash,output)
    if output.exists(): raise FileExistsError(output)
    tmp=output.with_name(output.name+".partial")
    if tmp.exists(): raise FileExistsError(tmp)
    observed=resolve(config_path,c["source"]["observed_db"]); ref=resolve(config_path,c["source"]["reference_1000_db"])
    before={"observed":fp(observed),"reference":fp(ref)}
    if before["observed"]["sha256"]!=c["source"]["observed_db_sha256"] or before["reference"]["sha256"]!=c["source"]["reference_1000_db_sha256"]: raise RuntimeError("source hash mismatch")
    for p in (observed,ref):
        q=sqlite3.connect(f"file:{p.as_posix()}?mode=ro",uri=True); q.execute("PRAGMA query_only=ON"); assert q.execute("PRAGMA query_only").fetchone()[0]==1; q.close()
    rng=random.Random(c["random_seed"]); draws=posterior_draws(resolve(config_path,c["source"]["probability_parameters"]),rng)
    pzero=draws.get("p_zero_result_rate",.50); prec=draws.get("p_session_final_recovery_rate",.73); pdetail=draws.get("p_card_h_rank1_detail_event",.738)
    profiles=make_profiles(n//2,rng,prec); run=f"SIM-{c['random_seed']}-{mode}-{n}"; start=datetime(2026,9,7,tzinfo=timezone.utc)
    try:
        db=sqlite3.connect(tmp); db.executescript(SCHEMA_SQL.read_text(encoding="utf-8")); insert_dims(db)
        db.execute("INSERT INTO SimulationRun VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)",(run,mode,"base",c["random_seed"],n,n//2,n//2,before["observed"]["sha256"],before["reference"]["sha256"],sha256(Path(__file__)),sha256(config_path),sha256(SCHEMA_SQL),json.dumps(packages(),sort_keys=True),json.dumps(draws,sort_keys=True),RUN_TIME))
        effects=c["effects"]["base"]
        for ix,p in enumerate(profiles):
          for arm in ("control","treatment"):
            uid=f"U{ix+1:05d}{'C' if arm=='control' else 'T'}"; sid=f"S{ix+1:05d}{'C' if arm=='control' else 'T'}"; policy="none" if arm=="control" else POLICIES[p["intent"]]
            stratum=f"{p['intent']}|{p['region']}|{p['state']}"; ip=1/len(POLICIES)
            db.execute("INSERT INTO ExperimentAssignment VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(uid,p["pair_id"],arm,stratum,p["intent"],ip,"intent-v1",run,c["random_seed"],"base",policy,p["cluster"],p["region"],p["state"],p["price"],p["option"],p["propensity"],p["base_recovery"],p["u_zero"],p["u_behavior"],p["u_recovery"],p["u_detail"],c["generation"]["lineage_policy"]))
            exposed=arm=="treatment"; selected=exposed and p["u_behavior"]<effects["proposal_select_prob"]; changed=selected and ((p["u_behavior"]*1.618)%1)<effects["condition_change_prob"]
            zero=p["u_zero"]<pzero; recovery_prob=min(.99,p["base_recovery"]+(effects["recovery_lift_pp"] if changed else 0)); recovered=zero and p["u_recovery"]<recovery_prob
            detail_prob=min(.99,pdetail+(effects["detail_lift_pp"] if changed else 0)); detail=recovered and p["u_detail"]<detail_prob
            searches=1+(1 if zero else 0)+(1 if zero and not recovered and p["propensity"]>2 else 0); searches=min(searches,c["generation"]["max_searches_per_session"])
            t=start+timedelta(seconds=ix*3); search_ids=[]; last=t
            db.execute("INSERT INTO ActionEvent VALUES(?,?,?,?,?,?,?,?,?)",(f"E-{uid}-000",run,uid,sid,None,"session_start",t.isoformat(),None,None))
            for seq in range(1,searches+1):
                if seq>1:
                    gap=max(c["generation"]["interarrival_min_seconds"],min(c["generation"]["interarrival_max_seconds"],int(rng.lognormvariate(3.1,.55)))); t=last+timedelta(seconds=gap)
                else: gap=None
                result=0 if zero and seq==1 else (rng.randrange(3,31) if recovered or not zero else 0)
                search_id=f"Q-{uid}-{seq:02d}"; search_ids.append(search_id); signature=f"{p['region']}|{p['state']}|{p['intent']}|{seq}|{ix%503}"
                db.execute("INSERT INTO Search VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(search_id,run,uid,p["pair_id"],sid,seq,t.isoformat(),p["region"],"related" if changed and seq>1 else "base",100000 if p["price"] else None,2 if p["option"] else None,result,signature))
                db.execute("INSERT INTO ActionEvent VALUES(?,?,?,?,?,?,?,?,?)",(f"E-{uid}-S{seq}",run,uid,sid,search_id,"search_submit",t.isoformat(),None,None))
                if seq==1 and exposed: db.execute("INSERT INTO ActionEvent VALUES(?,?,?,?,?,?,?,?,?)",(f"E-{uid}-X",run,uid,sid,search_id,"treatment_exposure",(t+timedelta(milliseconds=100)).isoformat(),None,policy))
                for rank in range(1,min(result,c["generation"]["max_exposures_per_positive_search"])+1):
                    hk=1+((ix*11+seq*7+rank)%60); rk=(hk-1)*2+1
                    db.execute("INSERT INTO ExposureBridge VALUES(?,?,?,?,?,?)",(f"X-{search_id}-{rank}",search_id,hk,rk,rank,(t+timedelta(milliseconds=rank*100)).isoformat()))
                if seq>1:
                    behavior="query" if changed and p["intent"]=="query_reframer" else ("relax" if changed else "same")
                    db.execute("INSERT INTO SearchTransition VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(f"T-{uid}-{seq-1}",run,uid,p["pair_id"],search_ids[-2],search_id,behavior,gap,int(exposed),int(selected),int(changed),int(recovered and seq==2),int(detail and seq==2)))
                last=t
            if detail:
                hk=1+((ix*11+2*7+1)%60); db.execute("INSERT INTO ActionEvent VALUES(?,?,?,?,?,?,?,?,?)",(f"E-{uid}-D",run,uid,sid,search_ids[-1],"hotel_detail_view",(last+timedelta(seconds=1)).isoformat(),hk,None))
            end=last+timedelta(seconds=2); db.execute("INSERT INTO ActionEvent VALUES(?,?,?,?,?,?,?,?,?)",(f"E-{uid}-END",run,uid,sid,None,"session_end",end.isoformat(),None,None))
            outcome="SG1" if not zero else ("SG2" if recovered and detail else ("SG3" if recovered else "SG4"))
            db.execute("INSERT INTO SessionSummary VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,run,uid,p["pair_id"],arm,stratum,p["intent"],policy,"base",c["random_seed"],start.isoformat(),end.isoformat(),searches,int(zero),int(recovered),int(detail),outcome))
        for k,v in {"data_class":"synthetic_scenario_not_observed_ab","lineage_policy":c["generation"]["lineage_policy"],"persistent_failure_observed_n":"43 (2/43)","query_reframer_detail_observed_n":"10","purpose":"sparse-outcome range and intervention-assumption sensitivity"}.items(): db.execute("INSERT INTO _generation_metadata VALUES(?,?)",(k,v))
        db.execute("UPDATE SimulationRun SET completed_at_utc=? WHERE simulation_run_id=?",(RUN_TIME,run)); db.commit()
        integrity=db.execute("PRAGMA integrity_check").fetchone()[0]; fk=len(db.execute("PRAGMA foreign_key_check").fetchall()); db.close()
        os.replace(tmp,output)
    except Exception:
        try:
            if 'db' in locals(): db.close()
        finally:
            if tmp.exists(): tmp.unlink()
        raise
    after={"observed":fp(observed),"reference":fp(ref)}
    if before!=after: raise RuntimeError("source changed during generation")
    return {"mode":mode,"users":n,"control":n//2,"treatment":n//2,"integrity":integrity,"foreign_key_violations":fk,"output":str(output),"output_sha256":sha256(output),"posterior_draws":draws}

def main()->None:
    ap=argparse.ArgumentParser(); ap.add_argument("--config",type=Path,default=HERE/"02_base_config_prod.yaml"); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--dry-run-users",type=int); ap.add_argument("--confirm-production",action="store_true"); ap.add_argument("--approved-config-sha256")
    a=ap.parse_args(); print(json.dumps(generate(a.config.resolve(),a.output.resolve(),a.dry_run_users,a.confirm_production,a.approved_config_sha256),ensure_ascii=True,indent=2))

if __name__=="__main__": main()
