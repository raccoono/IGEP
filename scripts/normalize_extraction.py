#!/usr/bin/env python3
"""Normalize honorific-bearing person references without altering raw runs."""

from __future__ import annotations
import argparse, json, re
from pathlib import Path

HONORIFIC = re.compile(r"^(?:ông|bà|cụ|anh|chị)\s+", re.IGNORECASE)
REF_KEYS={"subject","object","decedent","holder","testator","recipient","manager","person","related_person","related_decedent","actor","target","asserting_party"}
LIST_REF_KEYS={"target_decedents","witnesses","notified_parties","affected_persons","participants"}

def canonical(value: str) -> str:
    return HONORIFIC.sub("",value).strip()

def normalize(record: dict) -> dict:
    cid=str(record.get("case_id")); mapping={}
    for p in record.get("persons",[]):
        old=p["name"]
        if cid=="104" and old.casefold()=="bà t": new="T (vợ cũ)"
        elif cid=="104" and old=="T": new="T (con)"
        else: new=canonical(old)
        mapping[old]=new
        if old!=new and old not in p["aliases"]: p["aliases"].append(old)
        p["name"]=new
    def walk(value,key=None):
        if isinstance(value,dict):
            for k,v in value.items(): value[k]=walk(v,k)
        elif isinstance(value,list):
            return [walk(v,key) for v in value]
        elif isinstance(value,str) and (key in REF_KEYS or key in LIST_REF_KEYS):
            return mapping.get(value,canonical(value))
        return value
    return walk(record)

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--input",type=Path,required=True); ap.add_argument("--output",type=Path,required=True); ap.add_argument("--case-id",action="append"); a=ap.parse_args()
    rows=[normalize(json.loads(x)) for x in a.input.read_text(encoding="utf-8").splitlines() if x.strip()]
    if a.case_id:
        wanted=set(a.case_id); rows=[x for x in rows if str(x.get("case_id")) in wanted]
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in rows),encoding="utf-8")
    print(f"Normalized {len(rows)} predictions to {a.output}")
if __name__=="__main__": main()
