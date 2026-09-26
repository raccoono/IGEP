#!/usr/bin/env python3
"""Build the manually reviewed semantic-gold tranche for development cases.

The canonical migrated gold is never overwritten. Evidence is stored in a
sidecar because schema v2.2 intentionally has no evidence member on fact
objects. Add new reviewed cases to REVIEWED and EVIDENCE_QUOTES.
"""

from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path

from build_gold import graph_validation_errors, validate_instance


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/canonical/input.jsonl"
OUTPUT = ROOT / "data/canonical/dev_gold_reviewed.json"
EVIDENCE = ROOT / "data/review/dev_gold_evidence.jsonl"
AUDIT = ROOT / "data/review/dev_gold_audit.json"
SCHEMA = ROOT / "schema/valid.md"


def person(name, *, aliases=(), life="alive", death=None):
    return {"name": name, "aliases": list(aliases), "life_status": life,
            "death_time": death, "birth_time": None, "conception_time": None,
            "birth_status": "unknown", "age": None, "age_status": "unknown",
            "working_capacity": "unknown", "awareness_state": "unknown",
            "literacy_status": "unknown", "physical_limitation": None,
            "last_residence": None}


def rel(subject, relation, obj, qualifiers=(), status="active", start=None, end=None):
    return {"subject": subject, "relation": relation, "object": obj,
            "qualifiers": list(qualifiers), "relationship_status": status,
            "start_time": start, "end_time": end, "mutual_care": "not_mentioned"}


def asset(aid, typ, description, value, ownership="unknown", owners=()):
    return {"asset_id": aid, "asset_type": typ, "description": description,
            "value": value, "currency": "VND" if value is not None else None,
            "valuation_time": None, "ownership_type": ownership,
            "owners": [{"holder_type": "person", "holder": x,
                        "stated_share_ratio": None} for x in owners],
            "status": "existing"}


def estate(eid, decedent, assets, *, status="undivided"):
    return {"estate_id": eid, "decedent": decedent, "opening_place": None,
            "assets": assets, "obligations": [], "estate_roles": [],
            "distribution_status": status}


def action(aid, person_name, decedent, action_name, purpose, *, time=None):
    return {"action_id": aid, "person": person_name, "related_decedent": decedent,
            "action": action_name, "time": time, "form": "unknown",
            "notified_parties": [], "stated_purpose": purpose}


def event(eid, typ, person_name, estate_id, *, time=None, related_person=None, will=None):
    return {"event_id": eid, "event_type": typ, "person": person_name,
            "related_person": related_person, "related_estate_id": estate_id,
            "related_asset_id": None, "related_will_id": will, "time": time,
            "temporal_relation": "not_applicable", "details": {}}


def assertion(aid, subject_type, subject_ref, text, by="narrative", party=None):
    return {"assertion_id": aid, "subject_type": subject_type,
            "subject_ref": subject_ref, "assertion": text, "asserted_by": by,
            "asserting_party_type": "person" if party else None,
            "asserting_party": party}


def base(cid, targets, persons, relationships, estates, *, organizations=None,
         wills=None, actions=None, agreements=None, events=None, assertions=None):
    return {"schema_version": "2.2.0", "case_id": cid,
            "target_decedents": targets, "persons": persons,
            "organizations": organizations or [], "relationships": relationships,
            "estates": estates, "wills": wills or [],
            "inheritance_actions": actions or [], "conduct_events": [],
            "agreements": agreements or [], "events": events or [],
            "legal_assertions": assertions or []}


def disposition(did, recipient, ratio, asset_id):
    return {"disposition_id": did, "disposition_type": "appoint_heir",
            "recipient_type": "person", "recipient": recipient,
            "manager_type": None, "manager": None, "affected_persons": [],
            "scope": "share_ratio", "asset_ids": [asset_id],
            "share_ratio": ratio, "amount": None, "currency": None,
            "condition": None, "appointed_role": None}


def joint_will(wid, testator, asset_id, disposition_start):
    return {"will_id": wid, "testator": testator, "date": "2000",
            "medium": "written", "execution_method": "unknown",
            "authentication": {"type": "certified", "place": "UBND xã",
                                   "certifier": None, "time": "2000"},
            "witnesses": [], "will_facts": None,
            "relations_to_other_wills": [],
            "dispositions": [disposition(f"D{disposition_start}", "D", "1/2", asset_id),
                             disposition(f"D{disposition_start+1}", "H", "1/4", asset_id),
                             disposition(f"D{disposition_start+2}", "L", "1/4", asset_id)]}


REVIEWED = {}

# Case 133
p133 = [person("K", aliases=["Cụ K"]), person("M1", aliases=["cụ M1"], life="deceased", death="2001")]
p133 += [person(x, aliases=[a]) for x, a in [("K1","ông K1"),("M","ông M"),("H","bà H"),("H1","bà H1"),("T1","bà T1"),("N","bà N"),("N1","bà N1")]]
r133 = [rel("K", "spouse_of", "M1", [], "ended", end="2001")]
for child in ["K1","M","H","H1","T1","N","N1"]:
    r133 += [rel(child,"child_of","K"), rel(child,"child_of","M1")]
REVIEWED["133"] = base("133", ["M1"], p133, r133,
    [estate("E1","M1",[asset("A1","land_use_right","Phần di sản của M1 trong thửa đất số 119, trị giá được nêu là 917.150.000 đồng",917150000)])],
    actions=[action("IA1","K","M1","request_distribution","Yêu cầu chia di sản; xin nhận đất bằng hiện vật, thanh toán chênh lệch và xem xét công sức")],
    events=[event("EVT1","claim_filed","K","E1")],
    assertions=[assertion("LA1","person","M1","died_without_will")])

# Case 121
p121=[person("X",aliases=["Cụ X"],life="deceased",death="2022"),person("C",aliases=["cụ C"]),person("C1",aliases=["ông C1"],life="deceased",death="2020"),person("M",aliases=["ông M"]),person("H",aliases=["bà H"]),person("N",aliases=["bà N"]),person("M1"),person("T1"),person("T2")]
r121=[]
for child in ["C1","M","H"]: r121 += [rel(child,"child_of","X"),rel(child,"child_of","C")]
r121 += [rel("N","spouse_of","C1",[],"ended",end="2020")]
for child in ["M1","T1","T2"]: r121.append(rel(child,"child_of","C1"))
REVIEWED["121"] = base("121",["C1"],p121,r121,
    [estate("E1","C1",[asset("A1","other","Khối tài sản quy đổi do C1 tạo lập",3782100000)])],
    actions=[action("IA1","C","C1","request_distribution","Yêu cầu chia di sản theo pháp luật")],
    agreements=[{"agreement_id":"AG1","agreement_type":"other","participants":["M","H","C"],"form":"unknown","time":None,"asset_ids":[],"terms":"M và H tặng cho C toàn bộ kỷ phần họ nhận từ suất thừa kế của X"}],
    events=[event("EVT1","claim_filed","C","E1")],
    assertions=[assertion("LA1","person","C1","died_without_will")])

# Case 85
p85=[person("M",aliases=["Ông M"],life="deceased",death="2022"),person("H",aliases=["bà H"]),person("L"),person("T2"),person("T1",aliases=["cụ T1"]),person("T",aliases=["cụ T"])]
r85=[rel("M","spouse_of","H",[],"ended",end="2022")]
for child in ["L","T2"]: r85 += [rel(child,"child_of","M"),rel(child,"child_of","H")]
r85 += [rel("M","child_of","T1",["biological"]),rel("M","child_of","T",["biological"])]
REVIEWED["85"] = base("85",["M"],p85,r85,
    [estate("E1","M",[asset("A1","other","Khối tài sản chung gồm đất, nhà và tàu cá",3257259602,"marital_common_property",["M","H"])])],
    actions=[action("IA1","T1","M","renunciation","Từ chối và nhường kỷ phần cho H",time="2022"),action("IA2","L","M","renunciation","Từ chối và nhường kỷ phần cho H",time="2022"),action("IA3","T2","M","renunciation","Từ chối và nhường kỷ phần cho H",time="2022"),action("IA4","T","M","request_distribution","Yêu cầu chia theo pháp luật và nhận phần bằng tiền",time="2022")],
    events=[event("EVT1","claim_filed","H","E1")],
    assertions=[assertion("LA1","person","M","died_without_will"),assertion("LA2","distribution","E1","request_credit_for_creation_maintenance_and_preservation",by="party_claim",party="H")])

# Case 132: two testators used the same certified instrument; schema v2.2 requires one testator per will.
p132=[person("S",aliases=["Cụ S"],life="deceased",death="2008"),person("X",aliases=["cụ X"],life="deceased",death="2020"),person("D"),person("H"),person("L"),person("H3",life="deceased",death="1994")]
r132=[]
for child in ["D","H","L","H3"]: r132 += [rel(child,"child_of","S"),rel(child,"child_of","X")]
REVIEWED["132"] = base("132",["S","X"],p132,r132,
    [estate("E1","S",[asset("A1","land_use_right","Phần tài sản của S trong đất 79,2m2 và nhà thuộc khối di sản chung",None,"joint_property",["S","X"])]),estate("E2","X",[asset("A2","land_use_right","Phần tài sản của X trong đất 79,2m2 và nhà; phần 71,28m2 còn lại được định giá 8.039.457.000 đồng",8039457000,"joint_property",["S","X"])])],
    organizations=[{"name":"UBND xã","organization_type":"commune_committee","existence_status":"existing","termination_time":None}],
    wills=[joint_will("W1","S","A1",1),joint_will("W2","X","A2",4)],
    actions=[action("IA1","H","S","request_distribution","Yêu cầu chia theo nội dung di chúc",time="2023"),action("IA2","D","S","other","Đề nghị xem xét công sức bảo quản, duy trì di sản",time="2023")],
    agreements=[{"agreement_id":"AG1","agreement_type":"distribution_method","participants":["H","D","L"],"form":"unknown","time":"2023","asset_ids":["A1","A2"],"terms":"Đồng ý chia theo di chúc; trích 1/10 khối tài sản cho công sức của D"}],
    events=[event("EVT1","claim_filed","H","E1",time="2023",will="W1")],
    assertions=[assertion("LA1","distribution","AG1","one_tenth_awarded_to_D_for_preservation_effort")])

# Case 104 contains two distinct people both denoted T; canonical names disambiguate roles.
p104=[person("B",aliases=["Ông B"],life="deceased",death="2016"),person("T (vợ cũ)",aliases=["bà T"],life="unknown"),person("Y",aliases=["chị Y"]),person("T (con)",aliases=["T","chị T"]),person("Th",aliases=["bà Th"]),person("Tr",aliases=["anh Tr"]),person("Ph",aliases=["cụ Ph"]),person("Đ",aliases=["cụ Đ"])]
r104=[rel("B","spouse_of","T (vợ cũ)",["legal_marriage"],"ended",end="1991"),rel("B","spouse_of","Th",["legal_marriage"],"ended",start="1991",end="2016")]
for child in ["Y","T (con)"]: r104 += [rel(child,"child_of","B",["biological"]),rel(child,"child_of","T (vợ cũ)",["biological"])]
r104 += [rel("Tr","child_of","B",["biological"]),rel("Tr","child_of","Th",["biological"]),rel("B","child_of","Ph",["biological"]),rel("B","child_of","Đ",["biological"])]
REVIEWED["104"] = base("104",["B"],p104,r104,
    [estate("E1","B",[asset("A1","other","Quyền sử dụng đất và nhà hai tầng; phần hàng rào lấn mương không được tính giá trị",3923109500,"marital_common_property",["B","Th"])])],
    actions=[action("IA1","Ph","B","other","Nhường toàn bộ kỷ phần cho Th"),action("IA2","Đ","B","other","Nhường toàn bộ kỷ phần cho Th"),action("IA3","Y","B","other","Nhường toàn bộ kỷ phần cho Th"),action("IA4","Tr","B","other","Nhường toàn bộ kỷ phần cho Th"),action("IA5","T (con)","B","request_distribution","Yêu cầu nhận kỷ phần bằng tiền")],
    agreements=[{"agreement_id":"AG1","agreement_type":"in_kind_recipient","participants":["Th","Ph","Đ","Y","Tr"],"form":"unknown","time":None,"asset_ids":["A1"],"terms":"Th nhận nhà đất bằng hiện vật và thanh toán chênh lệch; Ph, Đ, Y, Tr nhường kỷ phần cho Th"}],
    events=[event("EVT1","claim_filed","Th","E1")],
    assertions=[assertion("LA1","person","B","died_without_will")])


EVIDENCE_QUOTES = {
    "133": ["Cụ K và cụ M1 (chết năm 2001, không có di chúc) có 7 người con chung: ông K1, ông M, bà H, bà H1, bà T1, bà N và bà N1.","Tài sản chung của hai cụ là thửa đất số 119 diện tích 313m2 (được định giá là 1.834.300.000 đồng, tài sản trên đất không yêu cầu giải quyết).","chia thừa kế phần di sản của cụ M1 (trị giá 917.150.000 đồng)","Cụ K xin nhận toàn bộ diện tích đất bằng hiện vật và sẽ thanh toán tiền cho các đồng thừa kế khác.","Cụ K cũng đề nghị Tòa án xem xét công sức bảo quản, tôn tạo tài sản."],
    "121": ["Cụ X (chết năm 2022) và cụ C có 3 người con chung là ông C1 (chết năm 2020), ông M và bà H.","Ông C1 có vợ là bà N và 3 người con là M1, T1, T2.","Sinh thời, ông C1 tạo lập được khối tài sản quy đổi có trị giá 3.782.100.000 đồng","Năm 2020, ông C1 qua đời không để lại di chúc.","cụ C khởi kiện yêu cầu chia di sản thừa kế của ông C1 theo pháp luật","ông M và bà H đều tự nguyện tặng cho cụ C toàn bộ kỷ phần thừa kế mà họ được hưởng lại từ suất thừa kế của cụ X"],
    "85": ["Ông M và bà H là vợ chồng, có hai con chung là L và T2.","Bố mẹ đẻ của ông M là cụ T1 và cụ T.","khối tài sản chung có tổng trị giá 3.257.259.602 đồng (bao gồm đất, nhà và tàu cá)","Năm 2022, ông M qua đời không để lại di chúc.","Cụ T1 cùng hai người con L và T2 đều đồng ý từ chối nhận di sản và nhường lại kỷ phần thừa kế của mình cho bà H.","cụ T không đồng ý nhường kỷ phần của mình, yêu cầu Tòa án chia thừa kế theo pháp luật và xin nhận phần của mình bằng tiền."],
    "132": ["Cụ S (chết 2008) và cụ X (chết 2020) có 4 người con chung: D, H, L, H3 (chết 1994, không vợ con).","Di sản của 2 cụ là một phần thửa đất (sau khi trừ đi phần lấn chiếm) còn lại 79,2m2 và một ngôi nhà.","Năm 2000, cụ S và cụ X lập di chúc có chứng thực của UBND xã với nội dung chia khối tài sản trên làm 4 phần, trong đó D được 2 phần, H và L mỗi người được 1 phần.","Năm 2023, H khởi kiện yêu cầu chia di sản theo nội dung di chúc.","D, L đều đồng ý chia theo di chúc, D đề nghị xem xét công sức bảo quản, duy trì di sản thừa kế của vợ chồng D.","Khối tài sản được trích 1/10 (tương đương 7,92m2) để trả công sức cho D, phần còn lại 71,28m2 có giá trị 8.039.457.000 đồng được đem ra phân chia."],
    "104": ["Ông B và bà T từng là vợ chồng, có hai con chung là Y và T.","Sau khi ly hôn, năm 1991, ông B kết hôn với bà Th và sinh được anh Tr.","Bố mẹ ruột của ông B là cụ Ph và cụ Đ vẫn còn sống.","khối tài sản chung gồm quyền sử dụng đất và một ngôi nhà 2 tầng. Tổng giá trị khối tài sản chung hợp pháp được định giá là 3.923.109.500 đồng","Năm 2016, ông B qua đời không để lại di chúc.","Bà Th khởi kiện yêu cầu chia di sản thừa kế của ông B","cụ Ph, cụ Đ, chị Y và anh Tr đều đồng ý nhường lại toàn bộ kỷ phần thừa kế của mình cho bà Th.","Riêng chị T không đồng ý nhường và yêu cầu được nhận kỷ phần thừa kế của mình bằng tiền."]
}


def main():
    inputs={str(x["case_id"]):x for x in map(json.loads,INPUT.read_text(encoding="utf-8").splitlines())}
    schema=json.loads(SCHEMA.read_text(encoding="utf-8"))
    errors=[]
    for cid,record in REVIEWED.items():
        errors += [f"case {cid}: {x}" for x in validate_instance(record,schema,schema)]
        errors += [f"case {cid}: {x}" for x in graph_validation_errors(record)]
    if errors: raise ValueError("\n".join(errors))
    OUTPUT.write_text(json.dumps([REVIEWED[x] for x in sorted(REVIEWED,key=int)],ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    def words(value):
        text=json.dumps(value,ensure_ascii=False) if not isinstance(value,str) else value
        text=unicodedata.normalize("NFKC",text).lower()
        return {x for x in re.findall(r"\w+",text,flags=re.UNICODE) if len(x)>1 and x not in {"null","unknown","active","person"}}
    def fact_objects(record):
        for i,x in enumerate(record["target_decedents"]): yield f"/target_decedents/{i}",x
        for key in ["persons","organizations","relationships","inheritance_actions","conduct_events","agreements","events","legal_assertions"]:
            for i,x in enumerate(record[key]): yield f"/{key}/{i}",x
        for i,e in enumerate(record["estates"]):
            yield f"/estates/{i}",e
            for j,x in enumerate(e["assets"]): yield f"/estates/{i}/assets/{j}",x
            for j,x in enumerate(e["obligations"]): yield f"/estates/{i}/obligations/{j}",x
        for i,w in enumerate(record["wills"]):
            yield f"/wills/{i}",w
            for j,x in enumerate(w["dispositions"]): yield f"/wills/{i}/dispositions/{j}",x
    evidence=[]
    for cid,quotes in EVIDENCE_QUOTES.items():
        text=inputs[cid]["query_text"]
        located=[]
        for quote in quotes:
            start=text.find(quote)
            if start<0: raise ValueError(f"case {cid}: evidence quote not exact: {quote}")
            located.append((quote,start,words(quote)))
        for i,(pointer,obj) in enumerate(fact_objects(REVIEWED[cid]),1):
            ow=words(obj)
            quote,start,_=max(located,key=lambda q:len(ow & q[2]))
            evidence.append({"case_id":cid,"evidence_id":f"EV{cid}_{i}","json_pointer":pointer,"start":start,"end":start+len(quote),"text":quote})
    EVIDENCE.write_text("".join(json.dumps(x,ensure_ascii=False)+"\n" for x in evidence),encoding="utf-8")
    AUDIT.write_text(json.dumps({"status":"semantic_review_draft_pending_author_or_expert_signoff","reviewed_case_ids":sorted(REVIEWED,key=int),"reviewed_count":len(REVIEWED),"remaining_development_cases":25,"schema_validation":"PASS","graph_validation":"PASS","evidence_sidecar":str(EVIDENCE.relative_to(ROOT)),"known_schema_issue":"Case 132 uses one will object per testator for a joint instrument; case 104 requires role-based disambiguation of duplicate name T."},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Wrote {len(REVIEWED)} reviewed cases and {len(evidence)} evidence spans")


if __name__ == "__main__": main()
