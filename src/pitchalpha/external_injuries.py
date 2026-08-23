"""Immutable ingestion and reconciliation for manually downloaded injury XLSX files."""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import uuid

from pitchalpha.dk_ingest import _candidates, match_player, normalize_name
from pitchalpha.slate_state import journal, load_slate_state, save_slate_state

REQUIRED_HEADERS={"player","team","pos","injury","status","est. return"}
STATUS_MAP={"GTD":"QUESTIONABLE","GAME TIME DECISION":"QUESTIONABLE","Q":"QUESTIONABLE","OUT":"OUT","O":"OUT","SUS":"SUSPENDED","SUSP":"SUSPENDED","SUSPENDED":"SUSPENDED","AVAILABLE":"AVAILABLE","ACTIVE":"AVAILABLE","HEALTHY":"AVAILABLE","IN":"AVAILABLE"}
ROUTED_ACTIONS=["investigate_dislocation","run_opportunity_models","run_fantasy_models","run_simulation","run_quality_assurance"]


def normalize_external_status(value):
    return STATUS_MAP.get(str(value or "").strip().upper(),"UNKNOWN")


def _cell(value):
    if value is None:return ""
    if isinstance(value,(datetime,date)):return value.isoformat()
    return str(value).strip()


def read_external_injury_xlsx(path):
    if Path(path).suffix.lower()!=".xlsx": raise ValueError("external injury report must be an .xlsx file")
    try: from openpyxl import load_workbook
    except ImportError as exc: raise RuntimeError("XLSX ingestion requires openpyxl") from exc
    workbook=load_workbook(path,read_only=True,data_only=True); sheet=workbook.active; iterator=sheet.iter_rows(values_only=True)
    try: headers=[str(x or "").strip().lower() for x in next(iterator)]
    except StopIteration: raise ValueError("external injury workbook is empty")
    missing=REQUIRED_HEADERS-set(headers)
    if missing: raise ValueError(f"missing required external injury columns: {sorted(missing)}")
    rows=[]
    for number,values in enumerate(iterator,2):
        row={header:_cell(value) for header,value in zip(headers,values)}
        if any(row.values()):rows.append({"row_number":number,**row})
    return rows


def _latest_state(con,slate_id=None):
    if slate_id:return load_slate_state(con,slate_id)
    row=con.execute("SELECT state_json FROM slate_states ORDER BY updated_at DESC LIMIT 1").fetchone(); return json.loads(row[0]) if row else None


def _projection(state,player_id):
    values=(state or {}).get("projections") or {}; direct=values.get(str(player_id)) or values.get(player_id)
    return direct or next((p for p in values.values() if str(p.get("player_id"))==str(player_id)),{})


def _previous_status(con,player_id,before):
    row=con.execute("SELECT status,status_raw FROM external_injury_observations WHERE api_football_player_id=? AND observation_timestamp<? ORDER BY observation_timestamp DESC LIMIT 1",[player_id,before]).fetchone()
    return {"normalized":row[0],"raw":row[1]} if row else None


def external_injury_comparison(con,slate_id=None,state=None):
    state=state or _latest_state(con,slate_id); slate_id=slate_id or (state or {}).get("slate_id")
    if not slate_id:return []
    output=[]
    for dkid,pid,name,team in con.execute("SELECT dk_player_id,api_football_player_id,dk_name,team FROM dfs_players WHERE slate_id=?",[slate_id]).fetchall():
        if pid is None:continue
        external=con.execute("SELECT status,status_raw,injury_description,observation_timestamp FROM external_injury_observations WHERE api_football_player_id=? ORDER BY observation_timestamp DESC LIMIT 1",[pid]).fetchone(); api=con.execute("SELECT injury_type,reason,observed_at FROM injuries WHERE player_id=? ORDER BY observed_at DESC LIMIT 1",[pid]).fetchone(); official=con.execute("SELECT started,observed_at FROM lineups WHERE player_id=? ORDER BY observed_at DESC LIMIT 1",[pid]).fetchone(); projection=_projection(state,pid)
        ext=external[0] if external else None; p_start=projection.get("p_start"); expected=projection.get("expected_minutes"); priority=reason=None
        if ext in {"OUT","SUSPENDED"} and float(p_start or 0)>.1:priority="HIGH"; reason=f"{ext} conflicts with non-trivial P(Start)"
        elif ext=="QUESTIONABLE" and float(p_start or 0)>=.75:priority="MEDIUM"; reason="QUESTIONABLE conflicts with high P(Start)"
        output.append({"dk_player_id":dkid,"player_id":pid,"player":name,"team":team,"api_football_injury_status":api[0] if api else None,"api_football_injury_reason":api[1] if api else None,"external_injury_status":ext,"external_status_raw":external[1] if external else None,"official_lineup_status":"STARTER" if official and official[0] else "SUBSTITUTE" if official else None,"p_start":p_start,"expected_minutes":expected,"disagreement_priority":priority,"disagreement_reason":reason})
    return output


def _record_changes(con,observations,slate_id,state):
    changes=[]; comparison={str(x["player_id"]):x for x in external_injury_comparison(con,slate_id,state)}
    for obs in observations:
        pid=obs["api_football_player_id"]
        if pid is None:continue
        previous=_previous_status(con,pid,obs["observation_timestamp"]); before=previous["normalized"] if previous else None
        if before==obs["status"]:continue
        current=comparison.get(str(pid),{}); priority=current.get("disagreement_priority") or ("HIGH" if obs["status"] in {"OUT","SUSPENDED"} else "MEDIUM" if obs["status"]=="QUESTIONABLE" else "LOW"); material=obs["status"] in {"QUESTIONABLE","OUT","SUSPENDED"}; actions=ROUTED_ACTIONS if material else ["run_quality_assurance"]
        event={"event_id":str(uuid.uuid4()),"timestamp":obs["observation_timestamp"].isoformat(),"slate_id":slate_id or "","event_type":"injury_status","entity_id":str(pid),"material":material,"changes":[{"field":"external_injury_status","before":before,"after":obs["status"],"status_raw":obs["status_raw"],"priority":priority}],"affected_actions":actions}
        con.execute("INSERT INTO change_events VALUES (?,?,?,?,?,?,?,?)",[event["event_id"],event["timestamp"],event["slate_id"],event["event_type"],event["entity_id"],event["material"],json.dumps(event["changes"]),json.dumps(actions)]); changes.append(event)
        if material:
            investigation={"source":"external_manual","external_status":obs["status"],"previous_status":before,"p_start":current.get("p_start"),"expected_minutes":current.get("expected_minutes"),"priority":priority,"reason":current.get("disagreement_reason") or "external injury status changed","required_flow":["disagreement_detection","investigation","quantitative_model_recomputation"]}
            con.execute("INSERT INTO anomaly_investigations VALUES (?,?,?,?,?,?,?,?)",[str(uuid.uuid4()),obs["observation_timestamp"],slate_id or "",str(pid),None,json.dumps(investigation),"opportunity_review","open"])
        if state and slate_id:journal(con,slate_id,"external_injury_change",f"external injury changed for {obs['player_name_raw']}",inputs={"before":before,"after":obs["status"],"source_file":obs["source_file"]},outputs={"priority":priority,"affected_actions":actions},result="review_routed",status="completed")
    return changes


def ingest_external_injuries(con,path,raw_dir,processed_dir,overrides_path=None,slate_id=None,now=None):
    path=Path(path)
    if not path.is_file():raise FileNotFoundError(path)
    observed=(now or datetime.now(timezone.utc)).astimezone(timezone.utc); digest=hashlib.sha256(path.read_bytes()).hexdigest(); batch=str(uuid.uuid4()); archive_dir=Path(raw_dir)/"external_injuries"/observed.strftime("%Y/%m/%d"); archive_dir.mkdir(parents=True,exist_ok=True); archived=archive_dir/f"{observed.strftime('%Y%m%dT%H%M%S%fZ')}_{digest[:12]}.xlsx"
    if archived.exists():raise FileExistsError(archived)
    shutil.copy2(path,archived); rows=read_external_injury_xlsx(archived); candidates=_candidates(con); overrides=json.loads(Path(overrides_path).read_text(encoding="utf-8")) if overrides_path and Path(overrides_path).exists() else {}
    for name,pid in con.execute("SELECT dk_name,api_football_player_id FROM player_mappings WHERE manual_override AND api_football_player_id IS NOT NULL QUALIFY row_number() OVER(PARTITION BY normalized_name ORDER BY created_at DESC)=1").fetchall():overrides.setdefault(normalize_name(name),int(pid))
    normalized=[]; duplicates=[]; seen=set()
    for raw in rows:
        key=(normalize_name(raw["player"]),raw["team"].upper(),raw["injury"].lower(),raw["status"].upper(),raw["est. return"].lower())
        if key in seen:duplicates.append({"row":raw["row_number"],"player":raw["player"],"team":raw["team"]}); continue
        seen.add(key); matched=match_player({"name":raw["player"],"team":raw["team"],"dk_player_id":None},candidates,overrides); normalized.append({"observation_id":str(uuid.uuid4()),"observation_timestamp":observed,"source":"external_manual","source_file":str(archived),"source_sha256":digest,"ingestion_batch_id":batch,"internal_player_id":matched.internal_player_id,"api_football_player_id":matched.api_football_player_id,"player_name_raw":raw["player"],"team_raw":raw["team"],"position_raw":raw["pos"],"injury_description":raw["injury"],"status_raw":raw["status"],"status":normalize_external_status(raw["status"]),"estimated_return_raw":raw["est. return"],"match_confidence":matched.confidence,"match_method":matched.method,"review":matched.review})
    con.execute("BEGIN TRANSACTION")
    try:
        fields=("observation_id","observation_timestamp","source","source_file","source_sha256","ingestion_batch_id","internal_player_id","api_football_player_id","player_name_raw","team_raw","position_raw","injury_description","status_raw","status","estimated_return_raw","match_confidence","match_method")
        for x in normalized:con.execute("INSERT INTO external_injury_observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",[x[k] for k in fields])
        con.execute("COMMIT")
    except Exception:con.execute("ROLLBACK"); raise
    state=_latest_state(con,slate_id); slate_id=slate_id or (state or {}).get("slate_id"); changes=_record_changes(con,normalized,slate_id,state); comparisons=external_injury_comparison(con,slate_id,state)
    if state and slate_id:
        state["external_injury_observations"]=[{k:v for k,v in x.items() if k not in {"review","source_sha256"}} for x in normalized]; state["injury_comparison"]={str(x["player_id"]):x for x in comparisons}; state.setdefault("pending_actions",[])
        for event in changes:
            for action in event["affected_actions"]:
                if action not in state["pending_actions"]:state["pending_actions"].append(action)
        warnings=[f"{x['disagreement_priority']} injury disagreement: {x['player']} — {x['disagreement_reason']}" for x in comparisons if x["disagreement_priority"]]; quality=state.setdefault("data_quality",{"status":"GREEN","failures":[],"warnings":[]}); quality["warnings"]=sorted(set(quality.get("warnings",[])+warnings)); quality["status"]="RED" if quality.get("failures") else "YELLOW" if quality["warnings"] else "GREEN"; state["data_freshness"]={**state.get("data_freshness",{}),"external_injuries":observed.isoformat()}; save_slate_state(con,state)
    review=[{"player":x["player_name_raw"],"team":x["team_raw"],"confidence":x["match_confidence"],"reason":x["match_method"]} for x in normalized if x["review"]]
    reconciliation=[{"player":x["player_name_raw"],"team":x["team_raw"],"internal_player_id":x["internal_player_id"],"api_football_player_id":x["api_football_player_id"],"match_confidence":x["match_confidence"],"match_method":x["match_method"],"manual_review":x["review"]} for x in normalized]
    result={"ingestion_batch_id":batch,"observation_timestamp":observed.isoformat(),"source":"external_manual","source_archive":str(archived),"source_sha256":digest,"total_rows":len(rows),"stored_rows":len(normalized),"matched":sum(x["api_football_player_id"] is not None for x in normalized),"unmatched":sum(x["match_method"] in {"unmatched","low_confidence"} for x in normalized),"ambiguous":sum(x["match_method"]=="ambiguous" for x in normalized),"duplicates":duplicates,"reconciliation":reconciliation,"manual_review":review,"changes":changes,"affected_players":sorted({x["entity_id"] for x in changes}),"downstream_actions":sorted({a for x in changes for a in x["affected_actions"]}),"comparison_conflicts":[x for x in comparisons if x["disagreement_priority"]]}
    reports=Path(processed_dir)/"reconciliation"; reports.mkdir(parents=True,exist_ok=True); report=reports/f"external_injuries_{observed.strftime('%Y%m%dT%H%M%SZ')}.md"; report.write_text(_report(result),encoding="utf-8"); result["report"]=str(report); return result


def _report(result):
    lines=["# External injury reconciliation","",f"Observed: {result['observation_timestamp']}",f"Rows: {result['total_rows']}",f"Matched: {result['matched']}",f"Unmatched: {result['unmatched']}",f"Ambiguous: {result['ambiguous']}",f"Duplicates ignored: {len(result['duplicates'])}",f"Status changes: {len(result['changes'])}","","## Manual review"]
    lines += [f"- {x['player']} ({x['team']}): {x['reason']} ({x['confidence']:.3f})" for x in result["manual_review"]] or ["- None"]
    lines += ["","## Reconciliation"]+[f"- {x['player']} ({x['team']}): {x['match_method']} confidence={x['match_confidence']:.3f} id={x['api_football_player_id']}" for x in result["reconciliation"]]
    lines += ["","## Source conflicts"]
    lines += [f"- {x['player']}: external {x['external_injury_status']}; P(Start) {x['p_start']}; {x['disagreement_priority']}" for x in result["comparison_conflicts"]] or ["- None"]
    return "\n".join(lines)+"\n"
